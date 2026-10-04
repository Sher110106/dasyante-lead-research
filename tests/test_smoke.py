import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SmokeTests(unittest.TestCase):
    def test_help_lists_research_review_and_enrich(self):
        result = subprocess.run(
            [sys.executable, "-m", "dasyante", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("research", result.stdout)
        self.assertIn("review", result.stdout)
        self.assertIn("enrich", result.stdout)

    def test_dry_run_counts_candidates_without_provider_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.csv"
            path.write_text("company_name,website\nAcme,https://acme.test\n")
            result = subprocess.run(
                [sys.executable, "-m", "dasyante", "research", "--input", str(path), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("1 candidate", result.stdout)
        self.assertIn("4 searches", result.stdout)

    def test_enrich_imports_apollo_csv_after_review_without_apollo_api(self):
        from dasyante.models import Candidate
        from dasyante.storage import Database

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "leads.db"
            database = Database(db_path)
            candidate_id = database.save_candidate(Candidate("Acme", "https://acme.test", candidate_id="acme_id"))
            database.set_score(candidate_id, 80, True)
            database.mark_reviewed(candidate_id)
            database.close()
            contacts = root / "contacts.csv"
            contacts.write_text("domain,first_name,last_name,title,email\nacme.test,Jane,Doe,CTO,jane@acme.test\n")
            result = subprocess.run(
                [sys.executable, "-m", "dasyante", "enrich", "--db", str(db_path), "--candidate-id", "acme_id", "--contacts", str(contacts)],
                env={**os.environ, "DASYANTE_ENV_FILE": str(root / "absent.env"), "HUNTER_API_KEY": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("imported 1 Apollo contact", result.stdout)
            database = Database(db_path)
            self.assertEqual(database.export()[0]["contacts"][0]["email"], "jane@acme.test")
            self.assertEqual(database.usage()["apollo_csv_import"], 1)
            self.assertNotIn("apollo_people_search", database.usage())
            database.close()


if __name__ == "__main__":
    unittest.main()
