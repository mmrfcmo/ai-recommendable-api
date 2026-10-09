
import unittest
from unittest.mock import patch

from app.services import trust_signal_engine
from app.services.trust_signal_engine import (
    SIGNALS,
    _score,
    _signal,
    _url,
    _tokens,
    _narrative_checks,
    _commercial_recommendation,
)


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

    def test_commercial_recommendation_thresholds_remain_unchanged(self):
        signals = [
            {"score": 20, "label": "Entity Clarity"},
            {"score": 30, "label": "Trust Evidence"},
            {"score": 60, "label": "External Validation"},
        ]

        self.assertEqual(
            _commercial_recommendation(49, signals)["recommended_treatment"],
            "Trust Transformation",
        )
        self.assertEqual(
            _commercial_recommendation(49, signals)["indicative_price"],
            "£995",
        )
        self.assertEqual(
            _commercial_recommendation(50, signals)["recommended_treatment"],
            "AI Trust Optimisation",
        )
        self.assertEqual(
            _commercial_recommendation(50, signals)["indicative_price"],
            "£1,249",
        )
        self.assertEqual(
            _commercial_recommendation(69, signals)["recommended_treatment"],
            "AI Trust Optimisation",
        )
        self.assertEqual(
            _commercial_recommendation(70, signals)["recommended_treatment"],
            "Advanced Visibility",
        )
        self.assertEqual(
            _commercial_recommendation(70, signals)["indicative_price"],
            "£1,995",
        )

    def test_signal_score_never_exceeds_maximum(self):
        self.assertEqual(_score([(True, 70), (True, 50)], 100), 100)
        self.assertEqual(_score([(True, 40), (False, 60)], 100), 40)

    def test_signal_percentage_is_normalised(self):
        signal = _signal(
            "test", "Test", 75, 100, ["Evidence"], gaps=["Gap"]
        )
        self.assertEqual(signal["score"], 75)
        self.assertEqual(signal["percentage"], 75)
        self.assertEqual(signal["gaps"], ["Gap"])

    def test_url_normalisation(self):
        self.assertEqual(_url("example.com"), "https://example.com")
        self.assertEqual(_url("http://example.com"), "http://example.com")

    def test_tokenisation_ignores_short_words(self):
        self.assertIn("company", _tokens("Our Company"))
        self.assertNotIn("we", _tokens("We Company"))

    def test_narrative_consistency_fully_aligned(self):
        checks = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", "Acme Roofing Ltd"
        )
        self.assertEqual(sum(points for _, _, points in checks), 100)

    def test_narrative_check_points_match_each_evidence_outcome(self):
        aligned = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", "Acme Roofing Ltd"
        )
        self.assertEqual([points for _, _, points in aligned], [20, 20, 60])
        self.assertEqual([passed for _, passed, _ in aligned], [True, True, True])

        no_structured_name = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", ""
        )
        self.assertEqual(
            [points for _, _, points in no_structured_name], [20, 20, 20]
        )

        conflicting_visible_identity = _narrative_checks(
            "Acme Roofing", "Different Plumbing", "Acme Roofing"
        )
        self.assertEqual(
            [points for _, _, points in conflicting_visible_identity],
            [20, 0, 0],
        )

        missing_visible_identity = _narrative_checks(
            "", "Acme Roofing", "Acme Roofing Ltd"
        )
        self.assertEqual(
            [points for _, _, points in missing_visible_identity], [0, 0, 0]
        )

    def test_narrative_consistency_without_structured_name(self):
        checks = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", ""
        )
        self.assertEqual(sum(points for _, _, points in checks), 60)

    def test_narrative_consistency_partial_structured_name(self):
        checks = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", "Acme Group"
        )
        self.assertEqual(sum(points for _, _, points in checks), 60)

    def test_narrative_consistency_conflicting_structured_name(self):
        checks = _narrative_checks(
            "Acme Roofing Ltd", "Acme Roofing", "Different Plumbing Ltd"
        )
        self.assertEqual(sum(points for _, _, points in checks), 40)

    def test_narrative_consistency_rejects_extra_conflicting_identity_tokens(self):
        checks = _narrative_checks(
            "Acme Roofing Ltd",
            "Acme Roofing",
            "Acme Roofing Plumbing Ltd",
        )
        self.assertEqual([points for _, _, points in checks], [20, 20, 20])

    def test_visible_identity_allows_generic_service_word_variation(self):
        checks = _narrative_checks(
            "Acme Roofing Services Ltd",
            "Acme Roofing",
            "Acme Roofing Ltd",
        )
        self.assertEqual([points for _, _, points in checks], [20, 20, 60])

    def test_visible_identity_ignores_leading_article(self):
        checks = _narrative_checks(
            "The Acme Roofing", "Acme Roofing", "Acme Roofing Ltd"
        )
        self.assertEqual([points for _, _, points in checks], [20, 20, 60])

    def test_visible_identity_allows_separated_seo_title_suffix(self):
        checks = _narrative_checks(
            "Acme Roofing | Trusted Roofers in London",
            "Acme Roofing",
            "Acme Roofing Ltd",
        )
        self.assertEqual([points for _, _, points in checks], [20, 20, 60])

    def test_narrative_consistency_conflicting_visible_identity(self):
        checks = _narrative_checks(
            "Acme Roofing", "Different Plumbing", ""
        )
        self.assertEqual(sum(points for _, _, points in checks), 20)

    def test_narrative_consistency_missing_visible_identity(self):
        checks = _narrative_checks(
            "", "Acme Roofing", "Acme Roofing Ltd"
        )
        self.assertEqual(sum(points for _, _, points in checks), 0)

    def test_basic_and_deep_use_same_engine_with_different_depth(self):
        pages = {
            "https://example.com/": """
                <html><head>
                <title>Example Business</title>
                <meta name="description" content="Example">
                <meta name="viewport" content="width=device-width">
                <link rel="canonical" href="https://example.com/">
                <script type="application/ld+json">
                {"@type":"Organization","name":"Example Business"}
                </script></head><body>
                <h1>Example Business</h1>
                <p>We provide services for local businesses.</p>
                <a href="/about">About</a>
                <a href="/services">Services</a>
                </body></html>
            """,
            "https://example.com/about": """
                <html><head><title>About Example Business</title></head>
                <body><h1>About Example Business</h1>
                <p>Example Business has years of experience serving clients.</p>
                <a href="/services">Services</a></body></html>
            """,
            "https://example.com/services": """
                <html><head><title>Services | Example Business</title></head>
                <body><h1>Our Services</h1>
                <p>Our services and solutions help professional clients.</p>
                </body></html>
            """,
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
                clean = (
                    url.rstrip("/")
                    if url != "https://example.com/"
                    else url
                )
                return Response(url, pages[clean])

        async def run():
            with patch.object(
                trust_signal_engine.httpx, "AsyncClient", Client
            ):
                basic = await trust_signal_engine.assess(
                    "https://example.com/", mode="basic"
                )
                deep = await trust_signal_engine.assess(
                    "https://example.com/", mode="deep"
                )
                return basic, deep

        import asyncio
        basic, deep = asyncio.run(run())

        self.assertTrue(basic["success"])
        self.assertTrue(deep["success"])
        self.assertEqual(basic["pages_assessed"], 1)
        self.assertGreaterEqual(deep["pages_assessed"], 3)
        self.assertEqual(
            [s["name"] for s in basic["signals"]],
            [s["name"] for s in deep["signals"]],
        )
        self.assertEqual(
            set(basic.keys()),
            {
                "success", "engine", "engine_version", "mode", "url",
                "business_name", "pages_assessed", "pages_discovered",
                "overall_score", "grade", "strongest_signal", "weakest_signal",
                "signals", "priority_improvements", "commercial_recommendation",
                "limitations",
            },
        )
        self.assertEqual(
            set(basic["commercial_recommendation"].keys()),
            {
                "recommended_treatment", "indicative_price", "reason",
                "priority_signals", "disclaimer",
            },
        )
        self.assertEqual(
            set(basic["signals"][0].keys()),
            {
                "name", "label", "score", "max_score", "percentage",
                "evidence", "limitations", "gaps", "diagnostic_context",
                "diagnostic_status", "diagnostic_summary",
            },
        )

    def test_redirect_resolved_url_is_returned(self):
        class Response:
            url = "https://example.com/"
            text = (
                "<html><head><title>Example</title></head>"
                "<body><h1>Example</h1></body></html>"
            )
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
            with patch.object(
                trust_signal_engine.httpx, "AsyncClient", Client
            ):
                return await trust_signal_engine.assess(
                    "http://old.example/", mode="basic"
                )

        import asyncio
        result = asyncio.run(run())

        self.assertTrue(result["success"])
        self.assertEqual(result["url"], "https://example.com/")

    def test_signal_weight_sets_total_100(self):
        weight_sets = {
            "knowledge_completeness": [17, 17, 17, 17, 16, 16],
            "trust_evidence": [25, 25, 25, 25],
            "technical_accessibility": [20, 20, 20, 20, 20],
            "external_validation": [34, 33, 33],
        }

        for weights in weight_sets.values():
            self.assertEqual(sum(weights), 100)

    def test_jsonld_business_name_inference(self):
        html = (
            '<html><head><title>Fallback Title</title>'
            '<script type="application/ld+json">'
            '{"@type":"Organization","name":"Structured Example Ltd"}'
            '</script></head><body><h1>Structured Example Ltd</h1>'
            '<p>Services and contact us.</p></body></html>'
        )

        class Response:
            url = "https://example.com/"
            text = html
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
            with patch.object(
                trust_signal_engine.httpx, "AsyncClient", Client
            ):
                return await trust_signal_engine.assess(
                    "https://example.com/", mode="basic"
                )

        import asyncio
        result = asyncio.run(run())

        self.assertTrue(result["success"])
        self.assertEqual(
            result["business_name"], "Structured Example Ltd"
        )

    def test_jsonld_business_name_inference_supports_industry_specific_types(self):
        for schema_type in ("RoofingContractor", "Dentist"):
            with self.subTest(schema_type=schema_type):
                html = (
                    '<html><head><title>Fallback Title</title>'
                    '<script type="application/ld+json">'
                    '{"@type":"' + schema_type + '","name":"Example Business Ltd"}'
                    '</script></head><body><h1>Example Business</h1>'
                    '<p>Services and contact us.</p></body></html>'
                )

                class Response:
                    url = "https://example.com/"
                    text = html
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
                    with patch.object(
                        trust_signal_engine.httpx, "AsyncClient", Client
                    ):
                        return await trust_signal_engine.assess(
                            "https://example.com/", mode="basic"
                        )

                import asyncio
                result = asyncio.run(run())
                self.assertTrue(result["success"])
                self.assertEqual(result["business_name"], "Example Business Ltd")

    def test_external_profile_evidence_is_detected(self):
        html = (
            '<html><head><title>Example</title></head><body>'
            '<h1>Example</h1><p>Our reviews and awards.</p>'
            '<a href="https://www.linkedin.com/company/example">'
            'LinkedIn</a></body></html>'
        )

        class Response:
            url = "https://example.com/"
            text = html
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
            with patch.object(
                trust_signal_engine.httpx, "AsyncClient", Client
            ):
                return await trust_signal_engine.assess(
                    "https://example.com/", mode="basic"
                )

        import asyncio
        result = asyncio.run(run())

        self.assertTrue(result["success"])
        external = next(
            s for s in result["signals"]
            if s["name"] == "external_validation"
        )
        self.assertIn(
            "Website exposes links/references to external profiles or authorities",
            external["evidence"],
        )

    def test_deep_mode_respects_eight_page_cap(self):
        links = "".join(
            f'<a href="/page{i}">Page {i}</a>'
            for i in range(1, 20)
        )
        pages = {
            "https://example.com/": (
                "<html><head><title>Example</title></head><body>"
                "<h1>Example</h1>"
                f"{links}</body></html>"
            )
        }

        for i in range(1, 20):
            pages[f"https://example.com/page{i}"] = (
                f'<html><head><title>Page {i}</title></head>'
                f'<body><h1>Page {i}</h1>'
                '<p>Services and experience.</p></body></html>'
            )

        class Response:
            def __init__(self, url):
                self.url = url
                self.text = pages[url]
                self.status_code = 200

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
                clean = (
                    url.rstrip("/")
                    if url != "https://example.com/"
                    else url
                )
                return Response(clean)

        async def run():
            with patch.object(
                trust_signal_engine.httpx, "AsyncClient", Client
            ):
                return await trust_signal_engine.assess(
                    "https://example.com/", mode="deep"
                )

        import asyncio
        result = asyncio.run(run())

        self.assertTrue(result["success"])
        self.assertEqual(result["pages_assessed"], 8)


if __name__ == "__main__":
    unittest.main()
