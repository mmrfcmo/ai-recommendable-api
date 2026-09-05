"""Discoverability Scanner - checks 6 trust signals."""
import re
import httpx
from bs4 import BeautifulSoup
from typing import Tuple, List
from app.schemas.discoverability import SignalResult

TRUST_SIGNALS = [
    ("schema_org", "Schema.org Markup", 20),
    ("nap_consistency", "NAP Consistency", 15),
    ("entity_clarity", "Entity Clarity", 15),
    ("content_depth", "Content Depth", 20),
    ("trust_signals", "Trust Signals", 15),
    ("technical_seo", "Technical SEO", 15),
]


async def scan_trust_signals(url: str) -> Tuple[List[SignalResult], int]:
    """Scan a website for discoverability trust signals."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = {}
    passed_count = 0

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()

            # 1. Schema.org markup
            has_schema = bool(re.search(r'application/ld\+json|schema\.org|itemscope|itemtype', html, re.IGNORECASE))
            schema_count = len(re.findall(r'application/ld\+json', html, re.IGNORECASE))
            if has_schema:
                if schema_count >= 3:
                    schema_score = 20
                elif schema_count == 2:
                    schema_score = 10
                else:
                    schema_score = 4
            else:
                schema_score = 0
            schema_detail = f"Schema.org markup found ({schema_count} blocks)" if has_schema else "No schema.org markup detected"
            results["schema_org"] = SignalResult(name="schema_org", passed=has_schema, score=schema_score, max_score=20, details=schema_detail)

            # 2. NAP consistency
            nap_found = bool(re.search(r'\d{10,15}|name.*address|phone|contact|tel:', text))
            nap_score = 15 if nap_found else 0
            nap_detail = "Contact info found" if nap_found else "No clear NAP (name, address, phone) found"
            results["nap_consistency"] = SignalResult(name="nap_consistency", passed=nap_found, score=nap_score, max_score=15, details=nap_detail)

            # 3. Entity clarity
            entity_signals = 0
            if re.search(r'(we are|we provide|we specialise|our services|about us|our mission|our team|our company)', text):
                entity_signals += 1
            if re.search(r'(founded|established|since|years|headquartered|based in|located in)', text):
                entity_signals += 1
            if soup.find("h1"):
                entity_signals += 1
            title_tag = soup.find("title")
            if title_tag and len(title_tag.get_text(strip=True)) > 5:
                entity_signals += 1
            entity_score = min(15, entity_signals * 4)
            entity_passed = entity_score >= 8
            entity_detail = f"Entity clarity: {entity_signals}/4 signals found" if entity_passed else "Business purpose unclear - add clear company description, founding details, and h1"
            results["entity_clarity"] = SignalResult(name="entity_clarity", passed=entity_passed, score=entity_score, max_score=15, details=entity_detail)

            # 4. Content depth
            content_signals = 0
            if re.search(r'(faq|frequently asked)', text):
                content_signals += 1
            if re.search(r'(blog|articles|resources|news)', text):
                content_signals += 1
            if re.search(r'(guide|how to|learn more|tutorial)', text):
                content_signals += 1
            if soup.find_all(["ul", "ol", "table"]):
                content_signals += 1
            word_count = len(text.split())
            if word_count > 800:
                content_signals += 1
            content_score = min(20, content_signals * 4)
            content_passed = content_score >= 10
            content_detail = f"Deep content found ({content_signals}/5 signals, ~{word_count} words)" if content_passed else f"Limited content depth ({content_signals}/5 signals, ~{word_count} words)"
            results["content_depth"] = SignalResult(name="content_depth", passed=content_passed, score=content_score, max_score=20, details=content_detail)

            # 5. Trust signals
            trust_signal_count = 0
            if re.search(r'(testimonial|review|rating|trustpilot)', text):
                trust_signal_count += 1
            if re.search(r'(case study|success story|results)', text):
                trust_signal_count += 1
            if re.search(r'(award|certified|accredited|recognised|featured in)', text):
                trust_signal_count += 1
            if re.search(r'(client|customer|member|subscriber)', text):
                trust_signal_count += 1
            trust_score = min(15, trust_signal_count * 4)
            trust_passed = trust_score >= 10
            trust_detail = f"Trust signals found ({trust_signal_count}/4)" if trust_passed else f"Few trust signals ({trust_signal_count}/4 found)"
            results["trust_signals"] = SignalResult(name="trust_signals", passed=trust_passed, score=trust_score, max_score=15, details=trust_detail)

            # 6. Technical SEO
            has_meta = bool(re.search(r'<meta[^>]+name=["\']description["\']', html, re.IGNORECASE))
            has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
            has_headings = bool(re.search(r'<h1[^>]*>', html, re.IGNORECASE))
            has_https = url.startswith("https")
            tech_count = sum([has_meta, has_viewport, has_headings, has_https])
            tech_score = min(15, tech_count * 4)
            tech_passed = tech_count >= 3
            meta_icon = "✓" if has_meta else "✗"
            viewport_icon = "✓" if has_viewport else "✗"
            h1_icon = "✓" if has_headings else "✗"
            tech_detail = f"Good technical SEO ({tech_count}/4)" if tech_passed else f"Tech SEO issues: meta desc ({meta_icon}), viewport ({viewport_icon}), h1 ({h1_icon})"
            results["technical_seo"] = SignalResult(name="technical_seo", passed=tech_passed, score=tech_score, max_score=15, details=tech_detail)

    except httpx.RequestError as e:
        for name, label, points in TRUST_SIGNALS:
            results[name] = SignalResult(name=name, passed=False, score=0, max_score=points, details=f"Connection failed: {str(e)[:80]}")
    except Exception as e:
        for name, label, points in TRUST_SIGNALS:
            results[name] = SignalResult(name=name, passed=False, score=0, max_score=points, details=f"Scan error: {str(e)[:80]}")

    passed_count = sum(1 for r in results.values() if r.passed)
    return list(results.values()), passed_count
