import csv
import tempfile
import unittest
from pathlib import Path

from dasyante.models import Candidate, Evidence
from dasyante.pipeline import load_candidates, extract_signals, enrich_qualified, research_candidate
from dasyante.storage import Database


class PipelineTests(unittest.TestCase):
    def test_public_job_board_urls_are_allowed_but_linkedin_is_not(self):
        from dasyante.pipeline import allowed_research_url

        self.assertTrue(allowed_research_url("https://boards.greenhouse.io/acme/jobs/1", "acme.test"))
        self.assertTrue(allowed_research_url("https://acme.test/careers", "acme.test"))
        self.assertFalse(allowed_research_url("https://www.linkedin.com/jobs/view/1", "acme.test"))
    def test_load_candidates_deduplicates_domains(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["company_name", "website"])
                writer.writeheader()
                writer.writerow({"company_name": "Acme", "website": "https://www.acme.test/"})
                writer.writerow({"company_name": "Acme duplicate", "website": "acme.test"})
            self.assertEqual(len(load_candidates(path)), 1)

    def test_extract_signals_keeps_verbatim_evidence(self):
        evidence = extract_signals(
            "Acme customer-facing agent supports persistent memory across customer sessions and includes LLM evaluation.",
            "https://acme.test/docs",
        )
        self.assertEqual(evidence["customer_facing_agent"][0].status, "yes")
        self.assertIn("persistent memory", evidence["persistent_memory"][0].quote.lower())

    def test_enrichment_rejects_unqualified_company(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "leads.db")
            self.addCleanup(db.close)
            with self.assertRaises(ValueError):
                enrich_qualified(db, "missing", lambda _: [])
    def test_research_counts_search_and_scrape_usage(self):
        from dasyante.providers import ScrapeResult, SearchResult

        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "leads.db")
            self.addCleanup(db.close)
            candidate = Candidate("Acme", "https://acme.test", candidate_id="acme_id")
            research_candidate(
                candidate,
                lambda query: [SearchResult("docs", "https://acme.test/docs")],
                lambda url: ScrapeResult(url, "customer-facing agent with persistent memory"),
                db,
            )
            self.assertEqual(db.usage()["tavily_search"], 4)
            self.assertEqual(db.usage()["tinyfish_fetch"], 1)


if __name__ == "__main__":
    unittest.main()
