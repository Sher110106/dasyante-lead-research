import unittest

from dasyante.models import Candidate, Evidence
from dasyante.scoring import qualify, score_signals


class ScoringTests(unittest.TestCase):
    def test_score_uses_evidence_strength_and_stays_bounded(self):
        evidence = {
            "customer_facing_agent": [Evidence("yes", "agent", "https://acme.test/agent", "T1")],
            "persistent_memory": [Evidence("yes", "memory", "https://acme.test/docs", "T2")],
            "reliability": [Evidence("yes", "evals", "https://acme.test/jobs", "T1")],
        }
        score = score_signals(evidence)
        self.assertEqual(score, 48)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_unknown_does_not_score_or_qualify(self):
        evidence = {
            "customer_facing_agent": [Evidence("yes", "agent", "https://acme.test/agent", "T1")],
            "persistent_memory": [Evidence("unknown", "", "https://acme.test", "T1")],
            "reliability": [Evidence("unknown", "", "https://acme.test", "T1")],
        }
        candidate = Candidate("Acme", "https://acme.test")
        self.assertEqual(score_signals(evidence), 18)
        self.assertFalse(qualify(candidate, evidence, threshold=65))

    def test_qualification_requires_direct_agent_and_pain_signals(self):
        evidence = {
            "customer_facing_agent": [Evidence("yes", "agent", "https://acme.test/agent", "T1")],
            "persistent_memory": [Evidence("yes", "memory", "https://acme.test/docs", "T1")],
            "reliability": [Evidence("yes", "evals", "https://acme.test/jobs", "T1")],
        }
        candidate = Candidate("Acme", "https://acme.test")
        self.assertTrue(qualify(candidate, evidence, threshold=50))


if __name__ == "__main__":
    unittest.main()
