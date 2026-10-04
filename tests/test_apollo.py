import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from dasyante.models import Candidate
from dasyante.pipeline import enrich_company_profile, research_candidate
from dasyante.providers import ApolloClient, ProviderConfigError, ProviderError, ScrapeResult, SearchResult
from dasyante.storage import Database


class ApolloProviderTests(unittest.TestCase):
    def test_missing_key_fails_before_network(self):
        with self.assertRaises(ProviderConfigError):
            ApolloClient("")

    def test_company_request_and_selected_metadata(self):
        def opener(request, timeout):
            parsed = urlparse(request.full_url)
            self.assertEqual(parsed.path, "/api/v1/organizations/enrich")
            self.assertEqual(parse_qs(parsed.query), {"domain": ["acme.test"]})
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.get_header("X-api-key"), "test-company-key")
            return io.BytesIO(json.dumps({"organization": {
                "id": "apollo-1", "name": "Acme", "primary_domain": "acme.test",
                "industry": "software", "estimated_num_employees": 150,
                "city": "Austin", "state": "Texas", "country": "United States",
                "total_funding_printed": "$10M", "latest_funding_round_type": "Series A",
                "latest_funding_round_date": "2026-01-01", "current_technologies": [{"name": "LangChain"}],
                "phone": "not-needed", "api_key": "must-not-persist",
            }}).encode())

        profile = ApolloClient("test-company-key", opener).enrich_company("acme.test")
        self.assertEqual(profile["employee_count"], 150)
        self.assertEqual(profile["location"], "Austin, Texas, United States")
        self.assertEqual(profile["technologies"], ["LangChain"])
        self.assertEqual(profile["total_funding"], "$10M")
        self.assertEqual(profile["apollo_id"], "apollo-1")
        self.assertNotIn("phone", profile)
        self.assertNotIn("api_key", profile)

    def test_organization_search_uses_trial_compatible_endpoint_and_selected_fields(self):
        def opener(request, timeout):
            self.assertEqual(urlparse(request.full_url).path, "/api/v1/organizations/search")
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.get_header("X-api-key"), "test-company-key")
            self.assertEqual(request.get_header("Content-type"), "application/json")
            self.assertEqual(json.loads(request.data), {"q_organization_name": "Acme", "page": 2, "per_page": 3})
            return io.BytesIO(json.dumps({"organizations": [{
                "id": "apollo-1", "name": "Acme", "primary_domain": "acme.test",
                "website_url": "https://acme.test", "industry": "software",
                "estimated_num_employees": 150, "phone": "must-not-persist",
            }], "pagination": {"page": 2, "total_pages": 4}}).encode())

        result = ApolloClient("test-company-key", opener).search_organizations("Acme", 2, 3)
        self.assertEqual(result["pagination"]["total_pages"], 4)
        self.assertEqual(result["organizations"][0]["domain"], "acme.test")
        self.assertNotIn("phone", result["organizations"][0])

    def test_no_match_is_explicit(self):
        client = ApolloClient("test-key", lambda request, timeout: io.BytesIO(b'{"organization": null}'))
        self.assertIsNone(client.enrich_company("acme.test"))

    def test_missing_organization_is_invalid_not_no_match(self):
        client = ApolloClient("test-key", lambda request, timeout: io.BytesIO(b'{}'))
        with self.assertRaises(ProviderError):
            client.enrich_company("acme.test")

    def test_mismatched_domain_is_not_saved_as_the_candidate(self):
        client = ApolloClient("test-key", lambda request, timeout: io.BytesIO(b'{"organization": {"name":"Other", "primary_domain":"other.test"}}'))
        with self.assertRaisesRegex(ProviderError, "domain"):
            client.enrich_company("acme.test")


class ApolloPipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Database(Path(self.directory.name) / "leads.db")
        self.addCleanup(self.database.close)
        self.candidate = Candidate("Acme", "https://acme.test", candidate_id="acme")
        self.candidate_id = self.database.save_candidate(self.candidate)
        self.finder = Mock(return_value={"name": "Acme", "domain": "acme.test", "industry": "software", "technologies": ["LangChain"]})

    def test_apollo_is_before_web_research_and_does_not_score_metadata(self):
        events = []

        def enrich(domain):
            events.append("apollo")
            return {"technologies": ["LangChain"], "industry": "healthcare"}

        def search(query):
            events.append("search")
            return [SearchResult("Docs", "https://acme.test/docs")]

        score = research_candidate(self.candidate, search, lambda url: ScrapeResult(url, "A normal product"), self.database, company_enrich=enrich)
        self.assertEqual(events[0], "apollo")
        self.assertEqual(score, 0)
        self.assertEqual(self.database.evidence_for(self.candidate_id), {})
        self.assertEqual(self.database.export()[0]["company_profile"]["status"], "success")
        self.assertEqual(self.database.export()[0]["contacts"], [])

    def test_fresh_profile_avoids_duplicate_credit_use(self):
        first = enrich_company_profile(self.database, self.candidate_id, self.finder)
        second = enrich_company_profile(self.database, self.candidate_id, self.finder)
        self.finder.assert_called_once_with("acme.test")
        self.assertEqual(first, second)
        self.assertEqual(self.database.usage()["apollo_company_enrich"], 1)

    def test_expired_profile_is_refetched(self):
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        self.database.connection.execute("UPDATE company_profiles SET fetched_at = ?", (old,))
        self.database.connection.commit()
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        self.assertEqual(self.finder.call_count, 2)

    def test_refresh_bypasses_fresh_cache(self):
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        enrich_company_profile(self.database, self.candidate_id, self.finder, refresh=True)
        self.assertEqual(self.finder.call_count, 2)

    def test_not_found_is_cached_and_does_not_invent_data(self):
        self.finder.return_value = None
        profile = enrich_company_profile(self.database, self.candidate_id, self.finder)
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        self.assertEqual(profile["status"], "not_found")
        self.assertIsNone(profile["data"])
        self.assertEqual(self.finder.call_count, 1)

    def test_failure_is_visible_nonfatal_and_retried(self):
        self.finder.side_effect = ProviderError("Apollo plan unavailable")
        score = research_candidate(self.candidate, lambda query: [], lambda url: None, self.database, company_enrich=self.finder)
        self.assertEqual(score, 0)
        profile = self.database.company_profile_for(self.candidate_id)
        self.assertEqual(profile["status"], "error")
        self.assertIn("plan unavailable", profile["error"])
        self.assertIsNone(profile["data"])
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        self.assertEqual(self.finder.call_count, 2)

    def test_failed_refresh_retains_old_data_with_warning(self):
        first = enrich_company_profile(self.database, self.candidate_id, self.finder)
        self.finder.side_effect = ProviderError("temporary outage")
        result = enrich_company_profile(self.database, self.candidate_id, self.finder, refresh=True)
        self.assertEqual(result["data"], first["data"])
        self.assertEqual(result["fetched_at"], first["fetched_at"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "temporary outage")

    def test_disabled_stage_does_not_call_apollo(self):
        research_candidate(self.candidate, lambda query: [], lambda url: None, self.database)
        self.assertNotIn("apollo_company_enrich", self.database.usage())
        self.assertIsNone(self.database.export()[0]["company_profile"])

    def test_company_profile_survives_reopening_existing_database(self):
        enrich_company_profile(self.database, self.candidate_id, self.finder)
        with_existing = Database(self.database.path)
        try:
            self.assertEqual(with_existing.export()[0]["company_profile"]["data"]["domain"], "acme.test")
            self.assertEqual(len(with_existing.export()), 1)
        finally:
            with_existing.close()

    def test_research_keeps_the_id_of_an_existing_company(self):
        new_input = Candidate("Acme renamed", "https://acme.test", candidate_id="csv-generated-id")
        research_candidate(new_input, lambda query: [], lambda url: None, self.database, company_enrich=self.finder)
        row = self.database.export()[0]
        self.assertEqual(row["id"], "acme")
        self.assertEqual(row["name"], "Acme renamed")
        self.assertEqual(row["company_profile"]["status"], "success")
