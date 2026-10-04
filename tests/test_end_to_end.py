import csv
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dasyante.cli import main
from dasyante.providers import ProviderError, ScrapeResult, SearchResult
from dasyante.storage import Database
from dasyante.web import WorkspaceHandler


FIXTURE_TEXT = (
    "Our customer-facing agent uses persistent memory and LLM evaluation. "
    "We hire an AI engineer and use LangGraph for recommendations. "
    "Our enterprise customers use the product we launched."
)
CANDIDATE_CSV = "company_name,website\nAcme Fixture,https://acme.test\n"
CONTACT_CSV = "domain,first_name,last_name,title,email\nacme.test,Test,Buyer,CTO,test@acme.test\n"


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.db_path = self.root / "leads.db"
        self.environment = patch.dict(os.environ, {
            "DASYANTE_ENV_FILE": str(self.root / "absent.env"),
            "TAVILY_API_KEY": "test-search",
            "TINYFISH_API_KEY": "test-fetch",
            "HUNTER_API_KEY": "",
            "APOLLO_API_KEY": "test-company",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def mock_providers(self, module):
        search = patch(f"{module}.TavilyClient")
        fetch = patch(f"{module}.TinyFishClient")
        apollo = patch(f"{module}.ApolloClient")
        search_mock = search.start()
        fetch_mock = fetch.start()
        apollo_mock = apollo.start()
        self.apollo_mock = apollo_mock
        self.addCleanup(search.stop)
        self.addCleanup(fetch.stop)
        self.addCleanup(apollo.stop)
        search_mock.return_value.search.return_value = [SearchResult("Docs", "https://acme.test/docs")]
        fetch_mock.return_value.scrape.side_effect = lambda url: ScrapeResult(url, FIXTURE_TEXT)
        apollo_mock.return_value.enrich_company.return_value = {"name": "Acme Fixture", "domain": "acme.test", "industry": "software", "employee_count": 150, "technologies": ["LangChain"]}
        return search_mock, fetch_mock

    def invoke(self, args, expected=0):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            result = main(args)
        self.assertEqual(result, expected, error.getvalue())
        self.last_error = error.getvalue()
        return output.getvalue()

    def test_cli_skip_cache_refresh_and_csv_context(self):
        self.mock_providers("dasyante.cli")
        candidates = self.root / "candidates.csv"
        candidates.write_text(CANDIDATE_CSV)
        args = ["research", "--input", str(candidates), "--db", str(self.db_path)]
        self.invoke([*args, "--skip-apollo"])
        self.apollo_mock.assert_not_called()
        self.invoke(args)
        self.invoke(args)
        self.assertEqual(self.apollo_mock.return_value.enrich_company.call_count, 1)
        self.invoke([*args, "--refresh-apollo"])
        self.assertEqual(self.apollo_mock.return_value.enrich_company.call_count, 2)
        dry_output = self.invoke([*args, "--dry-run"])
        self.assertIn("up to 1 Apollo company profiles", dry_output)
        self.assertEqual(self.apollo_mock.return_value.enrich_company.call_count, 2)
        output = self.root / "leads.csv"
        self.invoke(["export", "--db", str(self.db_path), "--output", str(output), "--format", "csv"])
        with output.open() as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["employee_count"], "150")
        self.assertEqual(row["technologies"], "LangChain")
        self.assertEqual(row["apollo_status"], "success")
        self.assertTrue(row["apollo_fetched_at"])

    def test_cli_warns_and_continues_when_apollo_fails(self):
        self.mock_providers("dasyante.cli")
        self.apollo_mock.return_value.enrich_company.side_effect = ProviderError("plan unavailable")
        candidates = self.root / "candidates.csv"
        candidates.write_text(CANDIDATE_CSV)
        output = self.invoke(["research", "--input", str(candidates), "--db", str(self.db_path)])
        self.assertIn("100/100", output)
        self.assertIn("warning:", self.last_error)
        self.assertIn("plan unavailable", self.last_error)

    def test_web_skip_refresh_dry_run_and_nonfatal_warning_response(self):
        self.mock_providers("dasyante.web")
        handler = object.__new__(WorkspaceHandler)
        handler.server = SimpleNamespace(database_path=str(self.db_path))
        with patch.object(handler, "_json") as response:
            handler._research({"csv": CANDIDATE_CSV, "dry_run": True})
            self.assertEqual(response.call_args.args[1]["apollo_company_profiles"], 1)
            self.apollo_mock.assert_not_called()
            handler._research({"csv": CANDIDATE_CSV, "skip_apollo": True})
            self.apollo_mock.assert_not_called()
            handler._research({"csv": CANDIDATE_CSV})
            handler._research({"csv": CANDIDATE_CSV})
            self.assertEqual(self.apollo_mock.return_value.enrich_company.call_count, 1)
            self.apollo_mock.return_value.enrich_company.side_effect = ProviderError("temporary outage")
            handler._research({"csv": CANDIDATE_CSV, "refresh_apollo": True})
            body = response.call_args.args[1]
            self.assertEqual(body["scores"]["Acme Fixture"], 100)
            self.assertIn("temporary outage", body["warnings"][0])
            self.assertEqual(body["dashboard"]["candidates"][0]["company_profile"]["status"], "error")
            self.assertEqual(body["dashboard"]["candidates"][0]["company_profile"]["data"]["employee_count"], 150)
        for value in ({"skip_apollo": True, "refresh_apollo": True}, {"skip_apollo": "yes"}):
            with self.assertRaises(ValueError):
                handler._research({"csv": CANDIDATE_CSV, **value})

    def test_cli_research_review_import_and_export(self):
        search, fetch = self.mock_providers("dasyante.cli")
        candidates, contacts = self.root / "candidates.csv", self.root / "contacts.csv"
        candidates.write_text(CANDIDATE_CSV)
        contacts.write_text(CONTACT_CSV)
        self.invoke(["research", "--input", str(candidates), "--db", str(self.db_path)])
        database = Database(self.db_path)
        row = database.export()[0]
        database.close()
        self.assertEqual(row["score"], 100)
        self.assertEqual(row["qualified"], 1)
        self.assertEqual(row["company_profile"]["data"]["employee_count"], 150)
        self.assertEqual(len(row["evidence"]), 8)
        self.assertEqual(search.return_value.search.call_count, 4)
        self.assertEqual(fetch.return_value.scrape.call_count, 1)
        candidate_args = ["--db", str(self.db_path), "--candidate-id", row["id"]]
        self.invoke(["enrich", *candidate_args, "--contacts", str(contacts)], expected=2)
        self.invoke(["review", *candidate_args])
        self.invoke(["enrich", *candidate_args, "--contacts", str(contacts)])
        exported = self.root / "leads.json"
        self.invoke(["export", "--db", str(self.db_path), "--output", str(exported)])
        result = json.loads(exported.read_text())[0]
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["company_profile"]["data"]["industry"], "software")
        self.assertEqual(result["contacts"][0]["email"], "test@acme.test")

    def test_http_research_review_hunter_import_and_dashboard(self):
        self.mock_providers("dasyante.web")
        server = ThreadingHTTPServer(("127.0.0.1", 0), WorkspaceHandler)
        server.database_path = str(self.db_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(path, payload=None, expected=200):
            body = json.dumps(payload).encode() if payload is not None else None
            req = Request(f"http://127.0.0.1:{server.server_port}{path}", data=body, headers={"Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=5) as response:
                    status, raw = response.status, response.read()
            except HTTPError as error:
                status, raw = error.code, error.read()
                error.close()
            self.assertEqual(status, expected, raw.decode())
            return json.loads(raw)

        try:
            self.assertTrue(request("/api/health")["ok"])
            request("/api/research", {"csv": CANDIDATE_CSV})
            candidate = request("/api/dashboard")["candidates"][0]
            self.assertEqual(candidate["score"], 100)
            self.assertEqual(candidate["company_profile"]["data"]["employee_count"], 150)
            path = f'/api/candidates/{candidate["id"]}'
            with patch.dict(os.environ, {"HUNTER_API_KEY": "test-hunter"}), patch("dasyante.web.HunterClient") as hunter:
                hunter.return_value.find_email.return_value = "test@acme.test"
                hunter.return_value.verify_email.return_value = "valid"
                contact_csv = "domain,first_name,last_name,title\nacme.test,Test,Buyer,CTO\n"
                request(path + "/contacts", {"csv": contact_csv}, expected=400)
                hunter.return_value.find_email.assert_not_called()
                request(path + "/review", {})
                result = request(path + "/contacts", {"csv": contact_csv})
                self.assertEqual(result["imported"], 1)
                self.assertEqual(result["candidate"]["contacts"][0]["email_status"], "valid")
                hunter.return_value.find_email.assert_called_once_with("acme.test", "Test", "Buyer")
                hunter.return_value.verify_email.assert_called_once_with("test@acme.test")
            dashboard = request("/api/dashboard")
            self.assertEqual(dashboard["stats"]["reviewed"], 1)
            self.assertEqual(dashboard["usage"]["tinyfish_fetch"], 1)
            self.assertEqual(dashboard["usage"]["apollo_company_enrich"], 1)
            self.assertEqual(dashboard["usage"]["hunter_email_verifier"], 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
