"""Enhanced Discoverability Scanner - checks 5 trust signals with Google Places API verification."""
import re
import httpx
from bs4 import BeautifulSoup
from typing import Tuple, List, Optional, Dict
from app.schemas.discoverability import SignalResult
import logging
from app.core.config import settings

logger = logging.getLogger("ai_recommendable.trust_scanner")



TRUST_SIGNALS = [
    ("schema_org", "Schema.org Markup", 20),
    ("nap_consistency", "NAP Consistency", 15),
    ("entity_clarity", "Entity Clarity", 15),
    ("content_depth", "Content Depth", 20),
    ("trust_signals", "Trust Signals", 15),
    ("technical_seo", "Technical SEO", 15),
]


async def check_google_places(business_name: str) -> Dict:
    """Check business data against Google Places API."""
    key = settings.google_places_api_key
    if not key:
        return {"found": False, "name": None, "address": None, "phone": None, 
                "rating": None, "reviews_count": None, "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.internationalPhoneNumber,places.rating,places.userRatingCount",
                    "Content-Type": "application/json",
                },
                json={
                    "textQuery": business_name,
                    "maxResultCount": 1,
                },
            )
            search_data = search_resp.json()
            
            if "error" in search_data:
                return {"found": False, "error": search_data["error"].get("message", "Unknown error")}
            
            places = search_data.get("places") or []
            if not places:
                return {"found": False, "error": "No Google Business Profile found"}
            
            p = places[0]
            return {
                "found": True,
                "place_id": p.get("id", ""),
                "name": (p.get("displayName") or {}).get("text", ""),
                "address": p.get("formattedAddress", ""),
                "phone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or "",
                "rating": p.get("rating"),
                "reviews_count": p.get("userRatingCount"),
            }
    except Exception as e:
        return {"found": False, "error": str(e)[:80]}


async def scan_trust_signals(url: str, business_name: str = None) -> Tuple[List[SignalResult], int]:
    """Scan a website for discoverability trust signals with Google Places verification."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = {}
    passed_count = 0
    
    # Extract business name from URL if not provided
    if not business_name:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        business_name = domain.replace("www.", "").split(".")[0].capitalize()

    # Fetch Google Places data in parallel with page scan
    gbp_data = await check_google_places(business_name)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()

            # 1. Schema.org markup
            has_schema = bool(re.search(r'application/ld\+json|schema\.org|itemscope|itemtype', html, re.IGNORECASE))
            schema_count = len(re.findall(r'application/ld\+json', html, re.IGNORECASE))
            
            # Validate schema by attempting to parse JSON-LD blocks
            valid_schema = 0
            if has_schema:
                jsonld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
                for block in jsonld_blocks:
                    try:
                        import json
                        data = json.loads(block.strip())
                        if "@context" in data and "@type" in data:
                            valid_schema += 1
                    except:
                        pass  # Invalid JSON-LD, don't count it
            
            schema_detail = f"Schema.org markup found ({schema_count} blocks, {valid_schema} valid)" if valid_schema > 0 else \
                           f"Schema.org markup found ({schema_count} blocks, but none valid)" if has_schema else \
                           "No schema.org markup detected"
            schema_score = min(20, valid_schema * 7) if valid_schema > 0 else (4 if has_schema else 0)
            results["schema_org"] = SignalResult(name="schema_org", passed=valid_schema > 0, score=schema_score, max_score=20, details=schema_detail)

            # 2. NAP consistency - enhanced with Google Places data
            nap_found = bool(re.search(r'\d{10,15}|name.*address|phone|contact|tel:', text))
            
            # Check if GBP data matches website NAP
            nap_issues = []
            if gbp_data.get("found"):
                gbp_name = gbp_data.get("name", "").lower()
                gbp_address = gbp_data.get("address", "").lower()
                gbp_phone = gbp_data.get("phone", "")
                
                # Check if business name on website matches GBP
                site_has_name = bool(re.search(re.escape(gbp_name[:20]), text)) if gbp_name else False
                if not site_has_name and gbp_name:
                    nap_issues.append(f"Business name may differ from Google Business Profile ('{gbp_data['name']}')")
                
                # Check if phone matches
                gbp_digits = re.sub(r"\D", "", gbp_phone)
                site_has_phone = bool(re.search(re.escape(gbp_digits[-10:]), text)) if gbp_digits else False
                if not site_has_phone and gbp_phone:
                    nap_issues.append(f"Phone number may differ from Google Business Profile")
                
                nap_detail = f"Google Business Profile found: {gbp_data['name']}"
                if nap_issues:
                    nap_detail += ". " + ". ".join(nap_issues)
                nap_score = 15 if nap_found and len(nap_issues) == 0 else (10 if nap_found else 5 if nap_found else 0)
            else:
                nap_detail = "Contact info found on website" if nap_found else "No clear NAP (name, address, phone) found"
                nap_score = 10 if nap_found else 0
                if gbp_data.get("error") and "No Google Business Profile" in gbp_data["error"]:
                    nap_issues.append("No Google Business Profile found")
                    nap_detail += ". No Google Business Profile detected"
            
            results["nap_consistency"] = SignalResult(name="nap_consistency", passed=nap_score >= 10, score=nap_score, max_score=15, details=nap_detail)

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

            # 5. Trust signals - enhanced with Google Places review data
            trust_signal_count = 0
            if re.search(r'(testimonial|review|rating|trustpilot)', text):
                trust_signal_count += 1
            if re.search(r'(case study|success story|results)', text):
                trust_signal_count += 1
            if re.search(r'(award|certified|accredited|recognised|featured in)', text):
                trust_signal_count += 1
            if re.search(r'(client|customer|member|subscriber)', text):
                trust_signal_count += 1
            
            # Add Google Places review data
            gbp_reviews = ""
            if gbp_data.get("found") and gbp_data.get("reviews_count") is not None:
                gbp_reviews = f" | Google rating: {gbp_data.get('rating', 'N/A')} ({gbp_data.get('reviews_count', 0)} reviews)"
                if gbp_data["reviews_count"] > 0:
                    trust_signal_count += 1  # Bonus signal for having real reviews
            
            trust_score = min(15, trust_signal_count * 3)
            trust_passed = trust_score >= 8
            trust_detail = f"Trust signals found ({trust_signal_count}/5)" if trust_passed else f"Few trust signals ({trust_signal_count}/5 found)"
            trust_detail += gbp_reviews
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
        import traceback
        logger.error(f"Scan error: {traceback.format_exc()}")
        for name, label, points in TRUST_SIGNALS:
            results[name] = SignalResult(name=name, passed=False, score=0, max_score=points, details=f"Scan error: {str(e)[:80]}")

    passed_count = sum(1 for r in results.values() if r.passed)
    return list(results.values()), passed_count