"""Enhanced Discoverability Scanner - checks 5 trust signals with Google Places API verification and multi-directory NAP."""
import re
import json
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Tuple, List, Optional, Dict
from urllib.parse import urlparse
from app.schemas.discoverability import SignalResult
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


def _normalise_phone(phone: str) -> str:
    """Normalise a phone number to comparable digits."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and not digits.startswith("00"):
        digits = "44" + digits[1:]
    return digits


def _normalise_address(addr: str) -> str:
    """Normalise an address for comparison."""
    if not addr:
        return ""
    return re.sub(r"\s+", " ", 
        addr.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("'", " ")
        .replace("&", "and")
        .replace("street", "st").replace("road", "rd")
        .replace("avenue", "ave").replace("boulevard", "blvd")
        .replace("drive", "dr").replace("lane", "ln")
        .replace("court", "ct").replace("place", "pl")
    ).strip()


def _extract_schema_nap(soup) -> Dict:
    """Extract structured NAP from LocalBusiness schema if available."""
    schemas = soup.find_all("script", type="application/ld+json")
    for script in schemas:
        try:
            data = json.loads(script.string.strip())
            # Handle @graph arrays
            items = data.get("@graph", [data]) if isinstance(data, dict) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") in ("LocalBusiness", "Organization", "Dentist", "MedicalBusiness", "HealthAndBeautyBusiness"):
                    name = item.get("name", "")
                    phone = item.get("telephone", "")
                    addr_obj = item.get("address", {})
                    if isinstance(addr_obj, dict):
                        street = addr_obj.get("streetAddress", "")
                        city = addr_obj.get("addressLocality", "")
                        postcode = addr_obj.get("postalCode", "")
                    else:
                        street = city = postcode = ""
                    return {"name": name, "phone": phone, "street": street, "city": city, "postcode": postcode, "source": "schema"}
        except:
            continue
    return {}


async def check_google_places(business_name: str) -> Dict:
    """Check business data against Google Places API with full field mask."""
    key = settings.google_places_api_key
    if not key:
        return {"found": False, "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.internationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri,places.types",
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
                "website": p.get("websiteUri", ""),
                "categories": p.get("types", []),
            }
    except Exception as e:
        return {"found": False, "error": str(e)[:80]}


async def check_nap_directory(name: str, address: str, phone: str, directory: str, query: str) -> Dict:
    """Check NAP against a specific directory via search."""
    # This is a simplified version - the full NAP Checker service has more detail
    return {"source": directory, "status": "Requires Manual Check"}


async def scan_trust_signals(url: str, business_name: str = None) -> Tuple[List[SignalResult], int]:
    """Scan a website for discoverability trust signals with multi-source verification."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = {}
    passed_count = 0
    
    if not business_name:
        domain = urlparse(url).netloc
        business_name = domain.replace("www.", "").split(".")[0].capitalize()

    # Fetch Google Places data
    gbp_data = await check_google_places(business_name)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True).lower()

            # ===== 1. SCHEMA ORG =====
            has_schema = bool(re.search(r'application/ld\+json|schema\.org|itemscope|itemtype', html, re.IGNORECASE))
            schema_count = len(re.findall(r'application/ld\+json', html, re.IGNORECASE))
            valid_schema = 0
            has_local_business = False
            
            if has_schema:
                jsonld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
                for block in jsonld_blocks:
                    try:
                        data = json.loads(block.strip())
                        items = data.get("@graph", [data]) if isinstance(data, dict) else [data]
                        for item in items:
                            if isinstance(item, dict) and "@context" in item and "@type" in item:
                                valid_schema += 1
                                if item["@type"] in ("LocalBusiness", "Organization", "Dentist", "MedicalBusiness", "HealthAndBeautyBusiness"):
                                    has_local_business = True
                    except:
                        pass
            
            schema_detail = f"Schema.org markup found ({schema_count} blocks, {valid_schema} valid)"
            if has_local_business:
                schema_detail += " including LocalBusiness"
            elif valid_schema > 0 and not has_local_business:
                schema_detail += " but missing LocalBusiness schema"
            
            schema_score = min(20, valid_schema * 5)
            if has_local_business:
                schema_score = max(schema_score, 15)  # Bonus for having LocalBusiness
            
            results["schema_org"] = SignalResult(
                name="schema_org", 
                passed=valid_schema > 0, 
                score=schema_score, 
                max_score=20, 
                details=schema_detail
            )

            # ===== 2. NAP CONSISTENCY - Enhanced =====
            # Extract NAP from schema first (most reliable)
            schema_nap = _extract_schema_nap(soup)
            
            # Extract NAP from page text as fallback
            text_nap = {}
            phone_match = re.search(r'(?:\+44|0)\d{10,12}|tel:[\d\s\-\(\)]{10,}', text)
            if phone_match:
                text_nap["phone"] = phone_match.group(0)
            
            address_match = re.search(r'(?:address|street|road|avenue|lane|drive|close)\s*:?[^.!]+', text, re.IGNORECASE)
            if address_match:
                text_nap["address"] = address_match.group(0)
            
            # Use schema NAP if available, otherwise text NAP
            website_nap = schema_nap if schema_nap.get("name") else text_nap
            
            # Compare with GBP data
            nap_issues = []
            nap_score = 0
            
            if gbp_data.get("found"):
                gbp_name = gbp_data.get("name", "")
                gbp_address = gbp_data.get("address", "")
                gbp_phone = gbp_data.get("phone", "")
                
                # Compare business name
                if schema_nap.get("name"):
                    if _normalise_address(schema_nap["name"]) != _normalise_address(gbp_name):
                        nap_issues.append(f"Business name differs from GBP: '{schema_nap['name']}' vs '{gbp_name}'")
                elif gbp_name.lower()[:15] not in text:
                    nap_issues.append(f"Business name '{gbp_name}' not clearly found on website")
                
                # Compare phone
                website_phone_digits = _normalise_phone(schema_nap.get("phone", ""))
                gbp_phone_digits = _normalise_phone(gbp_phone)
                if website_phone_digits and gbp_phone_digits and website_phone_digits != gbp_phone_digits:
                    nap_issues.append(f"Phone differs from GBP: website '{website_phone_digits}' vs GBP '{gbp_phone_digits}'")
                
                # Compare address fields
                if schema_nap.get("street"):
                    if _normalise_address(schema_nap["street"]) not in _normalise_address(gbp_address):
                        nap_issues.append(f"Street address may differ from GBP")
                if schema_nap.get("postcode"):
                    gbp_postcode = re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}', gbp_address, re.IGNORECASE)
                    if gbp_postcode:
                        if schema_nap["postcode"].replace(" ", "").upper() != gbp_postcode.group(0).replace(" ", "").upper():
                            nap_issues.append(f"Postcode differs from GBP")
                
                # Calculate score based on issues
                if len(nap_issues) == 0:
                    nap_score = 15  # Perfect match
                    nap_detail = f"NAP matches Google Business Profile: {gbp_name}"
                elif len(nap_issues) <= 2:
                    nap_score = 10  # Minor issues
                    nap_detail = f"Google Business Profile found: {gbp_name}. Issues: {'; '.join(nap_issues)}"
                else:
                    nap_score = 5  # Major issues
                    nap_detail = f"Google Business Profile found: {gbp_name}. Significant inconsistencies: {'; '.join(nap_issues)}"
            else:
                # No GBP found - score based on website NAP only
                if schema_nap.get("name") or (phone_match or address_match):
                    nap_score = 8
                    nap_detail = "NAP found on website but no Google Business Profile detected for verification"
                    if gbp_data.get("error") and "No Google" in gbp_data["error"]:
                        nap_detail += ". Consider creating or claiming your GBP listing"
                else:
                    nap_score = 0
                    nap_detail = "No clear NAP (name, address, phone) found on website"
            
            results["nap_consistency"] = SignalResult(
                name="nap_consistency", 
                passed=nap_score >= 10, 
                score=nap_score, 
                max_score=15, 
                details=nap_detail
            )

            # ===== 3. ENTITY CLARITY =====
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

            # ===== 4. CONTENT DEPTH =====
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

            # ===== 5. TRUST SIGNALS - Enhanced with real reviews =====
            trust_signal_count = 0
            if re.search(r'(testimonial|review|rating|trustpilot)', text):
                trust_signal_count += 1
            if re.search(r'(case study|success story|results)', text):
                trust_signal_count += 1
            if re.search(r'(award|certified|accredited|recognised|featured in)', text):
                trust_signal_count += 1
            if re.search(r'(client|customer|member|subscriber)', text):
                trust_signal_count += 1
            
            gbp_reviews = ""
            if gbp_data.get("found") and gbp_data.get("reviews_count") is not None:
                gbp_reviews = f" | Google rating: {gbp_data.get('rating', 'N/A')} ({gbp_data.get('reviews_count', 0)} reviews)"
                if gbp_data["reviews_count"] > 0:
                    trust_signal_count += 1
            
            trust_score = min(15, trust_signal_count * 3)
            trust_passed = trust_score >= 8
            trust_detail = f"Trust signals found ({trust_signal_count}/5)" if trust_passed else f"Few trust signals ({trust_signal_count}/5 found)"
            trust_detail += gbp_reviews
            results["trust_signals"] = SignalResult(name="trust_signals", passed=trust_passed, score=trust_score, max_score=15, details=trust_detail)

            # ===== 6. TECHNICAL SEO =====
            has_meta = bool(re.search(r'<meta[^>]+name=["\']description["\']', html, re.IGNORECASE))
            has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
            has_headings = bool(re.search(r'<h1[^>]*>', html, re.IGNORECASE))
            has_https = url.startswith("https")
            tech_count = sum([has_meta, has_viewport, has_headings, has_https])
            tech_score = min(15, tech_count * 4)
            tech_passed = tech_count >= 3
            tech_detail = f"Good technical SEO ({tech_count}/4)" if tech_passed else f"Tech SEO issues: meta desc ({'✓' if has_meta else '✗'}), viewport ({'✓' if has_viewport else '✗'}), h1 ({'✓' if has_headings else '✗'})"
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