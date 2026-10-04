from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import load_environment
from .pipeline import enrich_qualified, load_candidates, research_candidate
from .providers import ApolloClient, HunterClient, ProviderError, TavilyClient, TinyFishClient
from .storage import Database, open_database

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, default=str).encode("utf-8")


def _rows_from_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _import_contacts(database: Database, candidate_id: str, contact_csv: str) -> int:
    rows = _rows_from_csv(contact_csv)
    hunter_key = os.environ.get("HUNTER_API_KEY", "")
    hunter = HunterClient(hunter_key) if hunter_key else None

    def field(row: dict[str, str], *names: str) -> str:
        for name in names:
            value = row.get(name, "").strip()
            if value:
                return value
        return ""

    def finder(domain: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for row in rows:
            row_domain = field(row, "domain", "Domain", "Company Domain", "website", "Website").lower().removeprefix("www.")
            if field(row, "candidate_id", "Candidate ID") != candidate_id and row_domain != domain:
                continue
            first_name = field(row, "first_name", "First Name", "First name")
            last_name = field(row, "last_name", "Last Name", "Last name")
            if not first_name or not last_name:
                raise ValueError("contact CSV rows require first_name and last_name")
            email = field(row, "email", "Email", "Email Address")
            status = field(row, "email_status", "Email Status") or "unknown"
            if not email and hunter:
                email = hunter.find_email(domain, first_name, last_name)
                database.increment_usage("hunter_email_finder")
            if email and hunter:
                status = hunter.verify_email(email)
                database.increment_usage("hunter_email_verifier")
            results.append(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "title": field(row, "title", "Title"),
                    "email": email,
                    "email_status": status,
                    "linkedin_url": field(row, "linkedin_url", "LinkedIn URL", "Linkedin URL"),
                }
            )
            database.increment_usage("apollo_csv_import")
        if not results:
            raise ValueError("no Apollo-exported contacts matched this candidate")
        return results

    return enrich_qualified(database, candidate_id, finder)


def _dashboard(database: Database) -> dict[str, Any]:
    candidates = database.export()
    qualified = [candidate for candidate in candidates if candidate["qualified"]]
    reviewed = [candidate for candidate in candidates if candidate["reviewed"]]
    return {
        "stats": {
            "companies": len(candidates),
            "qualified": len(qualified),
            "reviewed": len(reviewed),
            "avg_score": round(sum(candidate["score"] for candidate in candidates) / len(candidates)) if candidates else 0,
        },
        "usage": database.usage(),
        "storage": database.backend_name,
        "providers": {"apollo_configured": bool(os.environ.get("APOLLO_API_KEY", ""))},
        "candidates": candidates,
    }


def _csv_export(rows: list[dict[str, Any]]) -> bytes:
    """Serialize the same company-context columns as the CLI export."""
    output = io.StringIO(newline="")
    profile_fields = ("industry", "employee_count", "location", "total_funding", "latest_funding_stage", "latest_funding_date", "technologies")
    fields = ("id", "name", "website", "domain", "score", "qualified", "reviewed", "apollo_status", "apollo_fetched_at", "apollo_error", *profile_fields)
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        profile = row.get("company_profile") or {}
        data = profile.get("data") or {}
        values = {key: row.get(key, "") for key in fields[:7]}
        values.update({key: data.get(key, "") for key in profile_fields})
        values["apollo_status"] = profile.get("status", "")
        values["apollo_fetched_at"] = profile.get("fetched_at", "")
        values["apollo_error"] = profile.get("error", "")
        values["technologies"] = "; ".join(data.get("technologies", []) or [])
        writer.writerow(values)
    return output.getvalue().encode("utf-8")


class WorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "DasyanteWorkspace/0.1"

    @property
    def database_path(self) -> Path:
        return Path(self.server.database_path)  # type: ignore[attr-defined]

    def _open_database(self) -> Database:
        """Open the configured request store.

        Local servers use SQLite by default.  The Vercel entrypoint overrides
        this hook so every request rebuilds its read model from JSONBin.
        """
        return open_database(self.database_path)

    @property
    def storage_backend(self) -> str:
        return os.environ.get("DASYANTE_STORAGE", "sqlite")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str = "application/json", headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, _json_bytes(value))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 2_000_000:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        payload = json.loads(raw or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:
        try:
            self._get()
        except ProviderError as exc:
            self._json(503, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "Unable to read the workspace"})

    def _get(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json(200, {"ok": True})
            return
        if parsed.path == "/api/dashboard":
            database = self._open_database()
            try:
                self._json(200, _dashboard(database))
            finally:
                database.close()
            return
        if parsed.path == "/api/export":
            output_format = parse_qs(parsed.query).get("format", ["json"])[0]
            if output_format not in {"json", "csv"}:
                self._json(400, {"error": "format must be json or csv"})
                return
            database = self._open_database()
            try:
                rows = database.export()
                if output_format == "json":
                    self._send(200, _json_bytes(rows), "application/json", {"Content-Disposition": 'attachment; filename="dasyante-leads.json"'})
                else:
                    self._send(200, _csv_export(rows), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="dasyante-leads.csv"'})
            finally:
                database.close()
            return
        if parsed.path.startswith("/api/candidates/"):
            candidate_id = parsed.path.rsplit("/", 1)[-1]
            database = self._open_database()
            try:
                candidate = next((item for item in database.export() if item["id"] == candidate_id), None)
                if candidate is None:
                    self._json(404, {"error": "candidate does not exist"})
                else:
                    self._json(200, candidate)
            finally:
                database.close()
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_file("index.html", "text/html; charset=utf-8")
            return
        if parsed.path in {"/app.js", "/styles.css"}:
            self._serve_file(parsed.path.lstrip("/"), "text/javascript; charset=utf-8" if parsed.path.endswith(".js") else "text/css; charset=utf-8")
            return
        self._json(404, {"error": "not found"})

    def _serve_file(self, name: str, content_type: str) -> None:
        path = (WEB_ROOT / name).resolve()
        if WEB_ROOT not in path.parents or not path.is_file():
            self._json(404, {"error": "asset not found"})
            return
        self._send(200, path.read_bytes(), content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/research":
                self._research(payload)
                return
            if parsed.path.startswith("/api/candidates/") and parsed.path.endswith("/review"):
                self._review(parsed.path.split("/")[-2])
                return
            if parsed.path.startswith("/api/candidates/") and parsed.path.endswith("/contacts"):
                self._contacts(parsed.path.split("/")[-2], payload)
                return
            self._json(404, {"error": "not found"})
        except ProviderError as exc:
            self._json(503, {"error": str(exc)})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": "Unable to update the workspace"})

    def _research(self, payload: dict[str, Any]) -> None:
        skip_apollo, refresh_apollo = payload.get("skip_apollo", False), payload.get("refresh_apollo", False)
        if not isinstance(skip_apollo, bool) or not isinstance(refresh_apollo, bool) or (skip_apollo and refresh_apollo):
            raise ValueError("Apollo skip and refresh must be booleans and cannot both be enabled")
        csv_text = str(payload.get("csv", "")).strip()
        if not csv_text:
            raise ValueError("CSV input is required")
        with tempfile.NamedTemporaryFile("w", suffix=".csv", encoding="utf-8", delete=False) as handle:
            handle.write(csv_text)
            input_path = Path(handle.name)
        try:
            candidates = load_candidates(input_path)
        finally:
            input_path.unlink(missing_ok=True)
        if not candidates:
            raise ValueError("CSV needs at least one company row")
        if self.storage_backend == "jsonbin" and len(candidates) > 1:
            raise ValueError("Hosted research accepts one company per request; submit the CSV through the workspace for batch progress")
        if payload.get("dry_run"):
            profile_count = len(candidates) if os.environ.get("APOLLO_API_KEY") and not skip_apollo else 0
            self._json(200, {"dry_run": True, "candidates": len(candidates), "searches": len(candidates) * 4, "triage_pages": len(candidates) * 2, "apollo_company_profiles": profile_count})
            return
        tavily = TavilyClient(os.environ.get("TAVILY_API_KEY", ""))
        tinyfish = TinyFishClient(os.environ.get("TINYFISH_API_KEY", ""))
        apollo_key = os.environ.get("APOLLO_API_KEY", "")
        apollo = ApolloClient(apollo_key) if apollo_key and not skip_apollo else None
        database = self._open_database()
        try:
            scores = {candidate.name: research_candidate(candidate, tavily.search, tinyfish.scrape, database,
                                                       company_enrich=apollo.enrich_company if apollo else None,
                                                       refresh_apollo=refresh_apollo) for candidate in candidates}
            warnings = []
            for candidate in candidates:
                stored = database.get_candidate_by_domain(candidate.domain)
                profile = database.company_profile_for(stored["id"]) if stored else None
                if apollo and profile and profile["status"] == "error":
                    warnings.append(f'{candidate.name}: Apollo profile unavailable: {profile["error"]}')
            # A hosted mutation is acknowledged only after its append-only
            # JSONBin record has been durably created.  SQLite's flush is a
            # harmless commit, so this keeps local behavior unchanged.
            database.flush()
            self._json(200, {"scores": scores, "warnings": warnings, "dashboard": _dashboard(database)})
        finally:
            database.close()

    def _review(self, candidate_id: str) -> None:
        database = self._open_database()
        try:
            row = database.get_candidate(candidate_id)
            if row is None:
                raise ValueError("candidate does not exist")
            if not row["qualified"]:
                raise ValueError("only qualified candidates can be reviewed")
            database.mark_reviewed(candidate_id)
            database.flush()
            self._json(200, {"ok": True, "candidate": next(item for item in database.export() if item["id"] == candidate_id)})
        finally:
            database.close()

    def _contacts(self, candidate_id: str, payload: dict[str, Any]) -> None:
        contact_csv = str(payload.get("csv", "")).strip()
        if not contact_csv:
            raise ValueError("contact CSV is required")
        database = self._open_database()
        try:
            count = _import_contacts(database, candidate_id, contact_csv)
            database.flush()
            self._json(200, {"ok": True, "imported": count, "candidate": next(item for item in database.export() if item["id"] == candidate_id)})
        finally:
            database.close()


def serve(database_path: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    load_environment()
    server = ThreadingHTTPServer((host, port), WorkspaceHandler)
    server.database_path = str(database_path)  # type: ignore[attr-defined]
    print(f"Dasyante workspace: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve(os.environ.get("DASYANTE_DB", "dasyante.db"))
