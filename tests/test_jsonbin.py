import copy
import io
import json
import os
import unittest
from unittest.mock import patch

from dasyante.jsonbin import JsonBinClient, JsonBinDatabase
from dasyante.models import Candidate, Evidence
from dasyante.providers import ProviderError
from dasyante.storage import open_database


class MemoryClient:
    def __init__(self):
        self.records = []
        self.fail_write = False

    def list_records(self, collection_id):
        return copy.deepcopy(self.records)

    def create_bin(self, collection_id, record):
        if self.fail_write:
            raise ProviderError("storage unavailable")
        self.records.append(copy.deepcopy(record))
        return f"{len(self.records):024x}"


class JsonBinTests(unittest.TestCase):
    def setUp(self):
        self.client = MemoryClient()
        self.collection = "a" * 24

    def database(self):
        database = JsonBinDatabase(self.collection, client=self.client)
        self.addCleanup(database.close)
        return database

    def test_persist_and_reopen_preserves_profiles_evidence_contacts_and_usage(self):
        db = self.database()
        cid = db.save_candidate(Candidate("Acme", "https://acme.test", candidate_id="acme"))
        db.add_evidence(cid, "persistent_memory", Evidence("yes", "memory", "https://acme.test"))
        db.set_score(cid, 77, True)
        db.mark_reviewed(cid)
        db.save_company_profile(cid, {"domain": "acme.test"}, "success")
        db.add_contact(cid, {"first_name": "Test", "last_name": "Buyer", "email": "test@acme.test", "email_status": "valid"})
        db.increment_usage("apollo_company_enrich")
        before = db.export()
        db.flush()
        reopened = self.database()
        self.assertEqual(reopened.export(), before)
        self.assertEqual(reopened.usage(), {"apollo_company_enrich": 1})
        self.assertEqual(len(self.client.records), 1)

    def test_independent_writers_do_not_replace_each_others_records(self):
        first, second = self.database(), self.database()
        first.save_candidate(Candidate("First", "https://first.test", candidate_id="first"))
        second.save_candidate(Candidate("Second", "https://second.test", candidate_id="second"))
        first.increment_usage("search")
        second.increment_usage("search")
        first.flush()
        second.flush()
        reopened = self.database()
        self.assertEqual(len(reopened.export()), 2)
        self.assertEqual(reopened.usage()["search"], 2)

    def test_duplicate_event_is_replayed_once(self):
        db = self.database()
        db.increment_usage("search")
        db.flush()
        self.client.records.append(copy.deepcopy(self.client.records[0]))
        self.assertEqual(self.database().usage()["search"], 1)

    def test_write_failure_does_not_report_success_or_fallback_to_disk(self):
        db = self.database()
        db.save_candidate(Candidate("Acme", "https://acme.test"))
        self.client.fail_write = True
        with self.assertRaises(ProviderError):
            db.flush()
        self.assertEqual(self.client.records, [])

    def test_read_only_request_does_not_create_bins(self):
        self.database().flush()
        self.assertEqual(self.client.records, [])

    def test_invalid_record_fails_closed(self):
        self.client.records.append({"not_an_app_record": True})
        with self.assertRaises(ProviderError):
            self.database()

    def test_snapshot_migration_retains_exact_profile_timestamps(self):
        profile = {"source": "Apollo", "status": "success", "data": {"domain": "acme.test"}, "fetched_at": "2026-10-01T00:00:00+00:00", "checked_at": "2026-10-01T00:00:00+00:00", "error": ""}
        self.client.records.append({"schema_version": 1, "event_id": "seed", "kind": "snapshot", "candidates": [{"id": "acme", "name": "Acme", "website": "https://acme.test", "domain": "acme.test", "score": 77, "qualified": 1, "reviewed": 1, "evidence": [], "contacts": [], "company_profile": profile}], "usage": {"search": 4}})
        db = self.database()
        self.assertEqual(db.company_profile_for("acme"), profile)
        self.assertEqual(db.get_candidate("acme")["reviewed"], 1)
        self.assertEqual(db.usage()["search"], 4)

    def test_storage_selection_never_silently_uses_sqlite_for_hosting(self):
        with patch.dict(os.environ, {"DASYANTE_STORAGE": "jsonbin", "JSONBIN_MASTER_KEY": "", "JSONBIN_COLLECTION_ID": ""}):
            with self.assertRaises(ProviderError):
                open_database(":memory:")

    def test_private_create_header_and_application_user_agent(self):
        def opener(request, timeout):
            self.assertEqual(request.get_header("X-master-key"), "test-master")
            self.assertEqual(request.get_header("X-bin-private"), "true")
            self.assertEqual(request.get_header("X-collection-id"), self.collection)
            self.assertIn("Dasyante", request.get_header("User-agent"))
            return io.BytesIO(json.dumps({"metadata": {"id": "b" * 24, "private": True}}).encode())
        client = JsonBinClient("test-master", opener=opener)
        self.assertEqual(client.create_bin(self.collection, {"hello": "world"}), "b" * 24)

    def test_collection_pagination_reads_all_bins(self):
        ids = [f"{n:024x}" for n in range(1, 13)]
        def opener(request, timeout):
            if request.full_url.endswith("/bins"):
                response = [{"record": i} for i in ids[:10]]
            elif "/bins/" in request.full_url:
                response = [{"record": i} for i in ids[10:]]
            else:
                response = {"record": {"id": request.full_url.split("/")[-2]}}
            return io.BytesIO(json.dumps(response).encode())
        self.assertEqual(len(JsonBinClient("test-master", opener=opener).list_records(self.collection)), 12)
