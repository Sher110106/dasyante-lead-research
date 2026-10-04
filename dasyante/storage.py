import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Candidate, Evidence


class Database:
    backend_name = "sqlite"
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                website TEXT NOT NULL,
                domain TEXT NOT NULL UNIQUE,
                linkedin_url TEXT NOT NULL DEFAULT '',
                score INTEGER NOT NULL DEFAULT 0,
                qualified INTEGER NOT NULL DEFAULT 0,
                reviewed INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL REFERENCES candidates(id),
                signal TEXT NOT NULL,
                status TEXT NOT NULL,
                quote TEXT NOT NULL,
                url TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                confidence REAL NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL REFERENCES candidates(id),
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                title TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                email_status TEXT NOT NULL DEFAULT 'unknown',
                linkedin_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS usage (
                name TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS company_profiles (
                candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
                data TEXT NOT NULL DEFAULT 'null',
                status TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT '',
                checked_at TEXT NOT NULL,
                error TEXT NOT NULL DEFAULT ''
            );
            """
        )
        self.connection.commit()

    def save_candidate(self, candidate: Candidate) -> str:
        candidate_id = candidate.candidate_id or candidate.domain.replace(".", "_")
        self.connection.execute(
            """
            INSERT INTO candidates(id, name, website, domain, linkedin_url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET name=excluded.name, website=excluded.website,
              linkedin_url=excluded.linkedin_url
            """,
            (candidate_id, candidate.name, candidate.website, candidate.domain, candidate.linkedin_url),
        )
        self.connection.commit()
        return self.get_candidate_by_domain(candidate.domain)["id"]

    def get_candidate(self, candidate_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()

    def get_candidate_by_domain(self, domain: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM candidates WHERE domain = ?", (domain,)).fetchone()

    def company_profile_for(self, candidate_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM company_profiles WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row is None:
            return None
        return {"source": "Apollo", "status": row["status"], "data": json.loads(row["data"]),
                "fetched_at": row["fetched_at"], "checked_at": row["checked_at"], "error": row["error"]}

    def save_company_profile(self, candidate_id: str, data: dict[str, Any] | None, status: str, error: str = "") -> None:
        if status not in {"success", "not_found", "error"}:
            raise ValueError("invalid company profile status")
        now = datetime.now(timezone.utc).isoformat()
        fetched_at = now
        if status == "error":
            previous = self.company_profile_for(candidate_id)
            data = previous["data"] if previous else None
            fetched_at = previous["fetched_at"] if previous else ""
        self.connection.execute(
            """INSERT INTO company_profiles(candidate_id, data, status, fetched_at, checked_at, error)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(candidate_id) DO UPDATE SET data=excluded.data, status=excluded.status,
                 fetched_at=excluded.fetched_at, checked_at=excluded.checked_at, error=excluded.error""",
            (candidate_id, json.dumps(data), status, fetched_at, now, error),
        )
        self.connection.commit()

    def add_evidence(self, candidate_id: str, signal: str, evidence: Evidence) -> None:
        self.connection.execute(
            "INSERT INTO evidence(candidate_id, signal, status, quote, url, source_tier, confidence, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (candidate_id, signal, evidence.status, evidence.quote, evidence.url, evidence.source_tier, evidence.confidence, evidence.fetched_at),
        )
        self.connection.commit()

    def set_score(self, candidate_id: str, score: int, qualified: bool) -> None:
        self.connection.execute(
            "UPDATE candidates SET score = ?, qualified = ? WHERE id = ?",
            (score, int(qualified), candidate_id),
        )
        self.connection.commit()

    def mark_reviewed(self, candidate_id: str, reviewed: bool = True) -> None:
        self.connection.execute("UPDATE candidates SET reviewed = ? WHERE id = ?", (int(reviewed), candidate_id))
        self.connection.commit()

    def evidence_for(self, candidate_id: str) -> dict[str, list[Evidence]]:
        rows = self.connection.execute("SELECT * FROM evidence WHERE candidate_id = ?", (candidate_id,)).fetchall()
        grouped: dict[str, list[Evidence]] = {}
        for row in rows:
            grouped.setdefault(row["signal"], []).append(
                Evidence(row["status"], row["quote"], row["url"], row["source_tier"], row["confidence"], row["fetched_at"])
            )
        return grouped

    def add_contact(self, candidate_id: str, contact: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO contacts(candidate_id, first_name, last_name, title, email, email_status, linkedin_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (candidate_id, contact.get("first_name", ""), contact.get("last_name", ""), contact.get("title", ""), contact.get("email", ""), contact.get("email_status", "unknown"), contact.get("linkedin_url", "")),
        )
        self.connection.commit()

    def increment_usage(self, name: str, amount: int = 1) -> None:
        self.connection.execute(
            "INSERT INTO usage(name, count) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET count = count + excluded.count",
            (name, amount),
        )
        self.connection.commit()

    def usage(self) -> dict[str, int]:
        return {row["name"]: row["count"] for row in self.connection.execute("SELECT name, count FROM usage")}

    def export(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM candidates ORDER BY score DESC, name").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["company_profile"] = self.company_profile_for(row["id"])
            item["evidence"] = [dict(e) for e in self.connection.execute("SELECT signal, status, quote, url, source_tier, confidence FROM evidence WHERE candidate_id = ?", (row["id"],))]
            item["contacts"] = [dict(c) for c in self.connection.execute("SELECT first_name, last_name, title, email, email_status, linkedin_url FROM contacts WHERE candidate_id = ?", (row["id"],))]
            result.append(item)
        return result

    def close(self) -> None:
        self.connection.close()

    def flush(self) -> None:
        self.connection.commit()


def open_database(path: str | Path) -> Database:
    backend = os.environ.get("DASYANTE_STORAGE", "sqlite")
    if backend == "sqlite":
        return Database(path)
    if backend == "jsonbin":
        from .jsonbin import JsonBinDatabase
        return JsonBinDatabase.from_environment()
    raise ValueError("DASYANTE_STORAGE must be sqlite or jsonbin")
