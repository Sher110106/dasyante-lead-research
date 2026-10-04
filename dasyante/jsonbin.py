"""Private append-only JSONBin persistence, with an in-memory SQLite read model.

Each request writes an independent mutation bin. There is no shared snapshot PUT
that can erase another serverless instance's concurrent updates.
"""

import json
import os
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.request import urlopen

from .models import Candidate, Evidence
from .providers import ProviderConfigError, ProviderError, _request_data
from .storage import Database


class JsonBinClient:
    def __init__(self, master_key: str, opener=urlopen):
        if not master_key:
            raise ProviderConfigError("JSONBIN_MASTER_KEY is required")
        self.master_key, self.opener = master_key, opener

    def request(self, method: str, path: str, payload=None, headers=None):
        return _request_data(method, "https://api.jsonbin.io/v3" + path, payload=payload,
                             headers={"X-Master-Key": self.master_key, "User-Agent": "DasyanteLeadResearch/0.1",
                                      "Accept": "application/json", "Content-Type": "application/json", **(headers or {})},
                             opener=self.opener)

    @staticmethod
    def validate_id(value: str) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{24}", value):
            raise ProviderConfigError("Invalid JSONBin collection or bin ID")
        return value

    def create_collection(self, name: str) -> str:
        response = self.request("POST", "/c", {}, {"X-Collection-Name": name})
        return self.validate_id(response.get("record"))

    def create_bin(self, collection_id: str, record: dict) -> str:
        self.validate_id(collection_id)
        if len(json.dumps(record).encode("utf-8")) > 90_000:
            raise ProviderError("Workspace write exceeds JSONBin's bin-size budget; reduce the request size")
        response = self.request("POST", "/b", record, {"X-Collection-Id": collection_id, "X-Bin-Private": "true", "X-Bin-Name": "dasyante-workspace"})
        metadata = response.get("metadata", {})
        if metadata.get("private") is not True:
            raise ProviderError("JSONBin did not confirm a private durable record")
        return self.validate_id(metadata.get("id"))

    def list_records(self, collection_id: str) -> list[dict]:
        self.validate_id(collection_id)
        records, seen = [], set()
        cursor = ""
        for _ in range(1000):
            suffix = f"/{cursor}" if cursor else ""
            page = self.request("GET", f"/c/{collection_id}/bins{suffix}", headers={"X-Sort-Order": "ascending"})
            if not isinstance(page, list):
                raise ProviderError("JSONBin returned an invalid collection listing")
            for entry in page:
                bin_id = self.validate_id(entry.get("record"))
                if bin_id in seen:
                    raise ProviderError("JSONBin returned a repeated pagination cursor")
                seen.add(bin_id)
                response = self.request("GET", f"/b/{bin_id}/latest")
                record = response.get("record")
                if not isinstance(record, dict):
                    raise ProviderError("JSONBin returned an invalid workspace record")
                records.append(record)
            if len(page) < 10:
                return records
            cursor = page[-1]["record"]
        raise ProviderError("Workspace history exceeds this prototype's read limit")


class JsonBinDatabase(Database):
    backend_name = "jsonbin"

    @classmethod
    def from_environment(cls):
        key = os.environ.get("JSONBIN_MASTER_KEY", "")
        collection = os.environ.get("JSONBIN_COLLECTION_ID", "")
        if not key or not collection:
            raise ProviderConfigError("JSONBIN_MASTER_KEY and JSONBIN_COLLECTION_ID are required; hosted storage cannot fall back to SQLite")
        return cls(collection, master_key=key)

    def __init__(self, collection_id: str, master_key: str = "", client=None):
        self.collection_id = JsonBinClient.validate_id(collection_id)
        self.client = client or JsonBinClient(master_key)
        self.pending = []
        self.event_id = uuid.uuid4().hex
        super().__init__(":memory:")
        self.replaying = True
        try:
            seen = set()
            for record in self.client.list_records(collection_id):
                if record.get("schema_version") != 1 or not record.get("event_id"):
                    raise ProviderError("Invalid JSONBin workspace history; no local fallback")
                if record["event_id"] in seen:
                    continue
                seen.add(record["event_id"])
                if record.get("kind") == "snapshot":
                    self.restore_snapshot(record)
                elif record.get("kind") == "mutation" and isinstance(record.get("operations"), list):
                    for operation in record["operations"]:
                        self.apply(operation)
                else:
                    raise ProviderError("Unsupported JSONBin workspace record")
        except Exception:
            super().close()
            raise
        finally:
            self.replaying = False

    def record(self, operation: dict):
        if not self.replaying:
            self.pending.append(operation)

    def apply(self, operation: dict):
        try:
            kind, args = operation["op"], operation["args"]
            if kind == "save_candidate":
                super().save_candidate(Candidate(**args[0]))
            elif kind == "add_evidence":
                super().add_evidence(args[0], args[1], Evidence(**args[2]))
            elif kind == "profile":
                self.restore_profile(args[0], args[1])
            elif kind in {"set_score", "mark_reviewed", "add_contact", "increment_usage"}:
                getattr(super(), kind)(*args)
            else:
                raise ProviderError("Unsupported workspace mutation")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Invalid stored workspace mutation") from exc

    def restore_profile(self, candidate_id: str, profile: dict):
        self.connection.execute("""INSERT INTO company_profiles(candidate_id,data,status,fetched_at,checked_at,error)
            VALUES (?,?,?,?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET data=excluded.data,status=excluded.status,
            fetched_at=excluded.fetched_at,checked_at=excluded.checked_at,error=excluded.error""",
            (candidate_id, json.dumps(profile["data"]), profile["status"], profile["fetched_at"], profile["checked_at"], profile["error"]))
        self.connection.commit()

    def restore_snapshot(self, record: dict):
        for row in record.get("candidates", []):
            cid = super().save_candidate(Candidate(row["name"], row["website"], row.get("linkedin_url", ""), row["id"]))
            super().set_score(cid, row["score"], bool(row["qualified"]))
            super().mark_reviewed(cid, bool(row["reviewed"]))
            for evidence in row.get("evidence", []):
                data = dict(evidence)
                signal = data.pop("signal")
                super().add_evidence(cid, signal, Evidence(**data))
            for contact in row.get("contacts", []):
                super().add_contact(cid, contact)
            if row.get("company_profile"):
                self.restore_profile(cid, row["company_profile"])
        for name, count in record.get("usage", {}).items():
            super().increment_usage(name, count)

    def save_candidate(self, candidate):
        cid = super().save_candidate(candidate)
        data = asdict(candidate)
        data["candidate_id"] = cid
        self.record({"op": "save_candidate", "args": [data]})
        return cid

    def add_evidence(self, candidate_id, signal, evidence):
        super().add_evidence(candidate_id, signal, evidence)
        self.record({"op": "add_evidence", "args": [candidate_id, signal, asdict(evidence)]})

    def set_score(self, candidate_id, score, qualified):
        super().set_score(candidate_id, score, qualified)
        self.record({"op": "set_score", "args": [candidate_id, score, qualified]})

    def mark_reviewed(self, candidate_id, reviewed=True):
        super().mark_reviewed(candidate_id, reviewed)
        self.record({"op": "mark_reviewed", "args": [candidate_id, reviewed]})

    def save_company_profile(self, candidate_id, data, status, error=""):
        super().save_company_profile(candidate_id, data, status, error)
        self.record({"op": "profile", "args": [candidate_id, self.company_profile_for(candidate_id)]})

    def add_contact(self, candidate_id, contact):
        super().add_contact(candidate_id, contact)
        self.record({"op": "add_contact", "args": [candidate_id, dict(contact)]})

    def increment_usage(self, name, amount=1):
        super().increment_usage(name, amount)
        self.record({"op": "increment_usage", "args": [name, amount]})

    def flush(self):
        if not self.pending:
            return
        self.client.create_bin(self.collection_id, {"schema_version": 1, "event_id": self.event_id,
            "kind": "mutation", "created_at": datetime.now(timezone.utc).isoformat(), "operations": self.pending})
        self.pending = []
        self.event_id = uuid.uuid4().hex


def snapshot_from_database(database: Database) -> dict[str, Any]:
    rows = database.export()
    for row in rows:
        row["evidence"] = [dict(entry) for entry in database.connection.execute(
            "SELECT signal,status,quote,url,source_tier,confidence,fetched_at FROM evidence WHERE candidate_id = ?", (row["id"],))]
    return {"schema_version": 1, "event_id": uuid.uuid4().hex, "kind": "snapshot",
            "candidates": rows, "usage": database.usage()}
