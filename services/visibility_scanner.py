"""AI Visibility Scanner - checks 6 trust signals."""
import re
import httpx
from bs4 import BeautifulSoup
from typing import Tuple, List, Dict
from app.schemas.visibility import SignalResult

AI_SIGNALS = [
    ("schema_org", "Schema.org Markup", 20),
    ("nap_consistency", "NAP Consistency", 15),
    ("entity_clarity", "Entity Clarity", 15),
    ("content_depth", "Content Depth", 20),
    ("trust_signals", "Trust Signals", 15),
    ("technical_seo", "Technical SEO", 15),
]


async def scan_visibility(url: str) -> Tuple[List[SignalResult], int]:
    """Scan a website for AI visibility signals."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = {}
    passed_count = 0
    total_signals = len(AI_SIGNALS)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()
            head_html = str(soup.find("head")) if soup.find("head") else ""

            # 1. Schema.org markup
            has_schema = bool(re.search(r'application/ld\+json|schema\.org|itemscope|itemtype', html, re.IGNORECASE))
            schema_detail = "Schema.org markup found" if has_schema else "No schema.org markup detected"
            results["schema_org"] = SignalResult(name="schema_org", passed=has_schema, score=20 if has_schema else 0, max_score=20, details=schema_detail)

            # 2. NAP consistency (name, address, phone)
            nap_found = bool(re.search(r'\b\d{10,15}\b|name.*address|phone|contact|📍', text))
            nap_detail = "Contact info found" if nap_found else "No clear NAP (name, address, phone) found"
            results["nap_consistency"] = SignalResult(name="nap_consistency", passed=nap_found, score=15 if nap_found else 0, max_score=15, details=nap_detail)

            # 3. Entity clarity (clear description of what the business does)
            entity_found = bool(re.search(r'(we are|we provide|we specialise|our services|about us|our mission)', text))
            entity_detail = "Business entity clearly described" if entity_found else "Business purpose unclear"
            results["entity_clarity"] = SignalResult(name="entity_clarity", passed=entity_found, score=15 if entity_found else 0, max_score=15, details=entity_detail)

            # 4. Content depth (FAQ, blog, resources)
            depth_found = bool(re.search(r'faq|frequently asked|blog|resources|guide|how to|learn more', text))
            depth_detail = "Deep content found (FAQ, blog, guides)" if depth_found else "Limited content depth"
            results["content_depth"] = SignalResult(name="content_depth", passed=depth_found, score=20 if depth_found else 0, max_score=20, details=depth_detail)

            # 5. Trust signals (testimonials, reviews, case studies)
            trust_found = bool(re.search(r'testimonial|review|case study|trustpilot|google review|rating', text))
            trust_detail = "Trust signals found" if trust_found else "No trust signals detected"
            results["trust_signals"] = SignalResult(name="trust_signals", passed=trust_found, score=15 if trust_found else 0, max_score=15, details=trust_detail)

            # 6. Technical SEO (meta tags, viewport, headings)
            has_meta = bool(re.search(r'<meta[^>]+name=["\']description["\']', html, re.IGNORECASE))
            has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
            has_headings = bool(re.search(r'<h1[^>]*>', html, re.IGNORECASE))
            tech_ok = has_meta and has_viewport and has_headings
            tech_detail = "Good technical SEO" if tech_ok else "Missing: description meta (" + ("✓" if has_meta else "✗") + "), viewport (" + ("✓" if has_viewport else "✗") + "), h1 (" + ("✓" if has_headings else "✗") + ")"
            results["technical_seo"] = SignalResult(name="technical_seo", passed=tech_ok, score=15 if tech_ok else 0, max_score=15, details=tech_detail)

    except httpx.RequestError as e:
        for name, label, points in AI_SIGNALS:
            results[name] = SignalResult(name=name, passed=False, score=0, max_score=points, details=f"Connection failed: {str(e)[:80]}")
    except Exception as e:
        for name, label, points in AI_SIGNALS:
            results[name] = SignalResult(name=name, passed=False, score=0, max_score=points, details=f"Scan error: {str(e)[:80]}")

    passed_count = sum(1 for r in results.values() if r.passed)
    return list(results.values()), passed_count
