import unittest
from unittest.mock import patch


from app.services import trust_signal_engine
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

    def test_basic_and_deep_use_same_engine_with_different_depth(self):
        pages = {
            "https://example.com/": """<html><head><title>Example Business</title><meta name="description" content="Example"><meta name="viewport" content="width=device-width"><link rel="canonical" href="https://example.com/"><script type="application/ld+json">{"@type":"Organization","name":"Example Business"}</script></head><body><h1>Example Business</h1><p>We provide services for local businesses.</p><a href="/about">About</a><a href="/services">Services</a></body></html>""",
            "https://example.com/about": """<html><head><title>About Example Business</title></head><body><h1>About Example Business</h1><p>Example Business has years of experience serving clients.</p><a href="/services">Services</a></body></html>""",
            "https://example.com/services": """<html><head><title>Services | Example Business</title></head><body><h1>Our Services</h1><p>Our services and solutions help professional clients.</p></body></html>""",
        }

        class Response:
            def __init__(self, url, text):
                self.url, self.text, self.status_code = url, text, 200
            def raise_for_status(self):
                return None

        class Client:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, url):
                clean = url.rstrip("/") if url != "https://example.com/" else url
                return Response(url, pages[clean])

        async def run():
            with patch.object(trust_signal_engine.httpx, "AsyncClient", Client):
                basic = await trust_signal_engine.assess("https://example.com/", mode="basic")
                deep = await trust_signal_engine.assess("https://example.com/", mode="deep")
                return basic, deep

        import asyncio
        basic, deep = asyncio.run(run())
        self.assertTrue(basic["success"])
        self.assertTrue(deep["success"])
        self.assertEqual(basic["pages_assessed"], 1)
        self.assertGreaterEqual(deep["pages_assessed"], 3)
        self.assertEqual([s["name"] for s in basic["signals"]], [s["name"] for s in deep["signals"]])

    def test_redirect_resolved_url_is_returned(self):
        class Response:
            url = "https://example.com/"
            text = "<html><head><title>Example</title></head><body><h1>Example</h1></body></html>"
            status_code = 200
            def raise_for_status(self):
                return None

        class Client:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, url):
                return Response()

        async def run():
            with patch.object(trust_signal_engine.httpx, "AsyncClient", Client):
                return await trust_signal_engine.assess("http://old.example/", mode="basic")

        import asyncio
        result = asyncio.run(run())
        self.assertTrue(result["success"])
        self.assertEqual(result["url"], "https://example.com/")

if __name__ == "__main__":
    unittest.main()
