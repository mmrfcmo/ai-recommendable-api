import unittest

from app.services.trust_signal_engine import SIGNALS, _score, _signal, _url, _tokens


class TrustSignalEngineTests(unittest.TestCase):
    def test_six_approved_signals(self):
        self.assertEqual(
            [key for key, _ in SIGNALS],
            [
                "entity_clarity",
                "knowledge_completeness",
                "trust_evidence",
                "technical_accessibility",
                "narrative_consistency",
                "external_validation",
            ],
        )

    def test_signal_score_never_exceeds_maximum(self):
        self.assertEqual(_score([(True, 70), (True, 50)], 100), 100)
        self.assertEqual(_score([(True, 40), (False, 60)], 100), 40)

    def test_signal_percentage_is_normalised(self):
        signal = _signal("test", "Test", 75, 100, ["Evidence"], gaps=["Gap"])
        self.assertEqual(signal["score"], 75)
        self.assertEqual(signal["percentage"], 75)
        self.assertEqual(signal["gaps"], ["Gap"])

    def test_url_normalisation(self):
        self.assertEqual(_url("example.com"), "https://example.com")
        self.assertEqual(_url("http://example.com"), "http://example.com")

    def test_tokenisation_ignores_short_words(self):
        self.assertIn("company", _tokens("Our Company"))
        self.assertNotIn("our", _tokens("Our Company"))


if __name__ == "__main__":
    unittest.main()
