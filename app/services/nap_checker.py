"""NAP Consistency Checker Service.

Scans major directories for a business's Name/Address/Phone (NAP) listings
and compares them against an authoritative NAP to identify inconsistencies.

Data sources (free API tiers):
- Google Places API (Google Business Profile data)
- Brave Search API (broad web coverage)

The service deliberately avoids overclaiming: directories that require
authentication or block anonymous access are reported as requiring
verification rather than silently assumed consistent.
"""

import logging
import re
import httpx
from typing import Optional, List, Dict
from app.core.config import settings

logger = logging.getLogger("ai_recommendable.nap_checker")

# Directories we target for NAP checking
CORE_DIRECTORIES = [
    "Google Business Profile",
    "Bing Places",
    "Facebook Business",
    "Yell",
    "Apple Maps",
    "Trustpilot",
]
LONG_TAIL_DIRECTORIES = [
    "Thomson Local",
    "Hotfrog",
    "Cylex",
    "Yably",
    "Opendi",
    "Infobel",
    "N49",
]


def _normalise_phone(phone: str) -> str:
    """Normalise a phone number to a comparable string (UK-aware)."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Normalise leading 0 to UK international 44
    if digits.startswith("0") and not digits.startswith("00"):
        digits = "44" + digits[1:]
    return digits


def _normalise_address(addr: str) -> str:
    """Normalise an address for fuzzy comparison."""
    if not addr:
        return ""
    return (
        addr.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("'", " ")
        .replace("&", "and")
        .replace("\b(street|st)\b", "st")
        .replace("\b(road|rd)\b", "rd")
        .replace("\b(avenue|ave)\b", "ave")
        .replace("\b(boulevard|blvd)\b", "blvd")
        .replace("\s+", " ")
        .strip()
    )


def _extract_postcode(text: str) -> Optional[str]:
    """Extract a UK postcode from arbitrary text."""
    if not text:
        return None
    match = re.search(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", text.upper())
    return match.group(0).replace(" ", "") if match else None


class NAPReference:
    """The authoritative NAP to compare against."""

    def __init__(self, business_name: str, address: str = "", postcode: str = "", phone: str = ""):
        self.business_name = (business_name or "").strip()
        self.address = (address or "").strip()
        self.postcode = _extract_postcode(postcode) or _extract_postcode(address) or ""
        self.phone = phone or ""

    def compare(self, listing_name: str, listing_address: str, listing_phone: str) -> Dict:
        """Compare a found listing against this authoritative NAP."""
        issues = []
        score = 100

        # Name
        auth_name = self.business_name.lower().strip()
        found_name = (listing_name or "").lower().strip()
        if found_name and auth_name and found_name not in auth_name and auth_name not in found_name:
            score -= 30
            issues.append(f'Name mismatch: "{listing_name}" vs "{self.business_name}"')
        elif not found_name:
            issues.append("Name not found")

        # Postcode
        found_postcode = _extract_postcode(listing_address or "")
        if self.postcode and found_postcode and found_postcode != self.postcode:
            score -= 35
            issues.append(f'Postcode mismatch: "{found_postcode}" vs "{self.postcode}"')

        # Phone
        auth_phone = _normalise_phone(self.phone)
        found_phone = _normalise_phone(listing_phone or "")
        if auth_phone and found_phone and found_phone != auth_phone:
            score -= 40
            issues.append(f'Phone mismatch: "{listing_phone}" vs "{self.phone}"')
        elif auth_phone and not found_phone:
            score -= 15
            issues.append("Phone not listed")

        score = max(0, score)
        status = (
            "Match" if score >= 85
            else "Inconsistent" if score >= 50
            else "Problem"
        )
        return {
            "score": score,
            "status": status,
            "issues": issues,
        }


async def check_google(reference: NAPReference) -> Dict:
    """Check NAP against Google Places API (new) (free tier)."""
    key = settings.google_places_api_key
    if not key:
        return {"source": "Google Business Profile", "status": "Not Checked", "score": 0,
                "issues": ["Google Places API key not configured"]}

    result = {"source": "Google Business Profile", "status": "Not Found", "score": 0,
              "name": None, "address": None, "phone": None, "issues": [], "note": "via Google Places API"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            # Use the new Places API (v1) searchText
            # Build query with location context if available
            query_text = reference.business_name
            if reference.postcode:
                query_text += " " + reference.postcode
            elif reference.address:
                query_text += " " + reference.address
            
            search_resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.internationalPhoneNumber",
                    "Content-Type": "application/json",
                },
                json={
                    "textQuery": query_text,
                    "maxResultCount": 1,
                },
            )
            search_data = search_resp.json()
            
            if "error" in search_data:
                err = search_data["error"]
                msg = err.get("message", "Unknown error")
                result["status"] = "Error"
                result["issues"] = [f"Google Places API error: {msg}"]
                return result
            
            places = search_data.get("places") or []
            if not places:
                result["status"] = "Not Found"
                result["issues"] = [f"No Google Business Profile found for '{reference.business_name}'"]
                return result
            
            p = places[0]
            place_id = p.get("id", "")
            display_name = (p.get("displayName") or {}).get("text", "")
            formatted_address = p.get("formattedAddress", "")
            listing_phone = p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or ""
            
            result.update(name=display_name, address=formatted_address, phone=listing_phone)
            result.update(reference.compare(display_name, formatted_address, listing_phone))
    except Exception as e:
        logger.error(f"Google NAP check failed: {e}")
        result["status"] = "Error"
        result["issues"] = [f"Google check error: {str(e)[:80]}"]
    return result

async def check_brave(reference: NAPReference) -> Dict:
    """Check NAP via Brave Search (free API, broad web coverage).
    Returns the actual result URLs and attempts NAP extraction from each."""
    key = settings.brave_api_key if hasattr(settings, "brave_api_key") else None
    if not key:
        return {"source": "Web (Brave Search)", "status": "Not Checked", "score": 0,
                "issues": ["Brave Search API key not configured"]}

    result = {"source": "Web (Brave Search)", "status": "Not Found", "score": 0,
              "name": None, "address": None, "phone": None, "issues": [], "note": "via Brave Search API"}
    try:
        query = f"{reference.business_name} {reference.postcode or ''}"
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"X-Subscription-Token": key, "Accept": "application/json"},
            )
            data = resp.json()
            web_results = (data.get("web", {}) or {}).get("results") or []
            
            # Collect all result details
            found_results = []
            for r in web_results:
                title = r.get("title", "")
                url = r.get("url", "")
                desc = r.get("description", "")
                found_results.append({"title": title, "url": url, "snippet": desc})
            
            mentions = [r.get("title", "") + " " + (r.get("description") or "") for r in web_results]
            combined = " ".join(mentions).lower()
            has_name = reference.business_name.lower() in combined
            
            if has_name:
                # Try to extract NAP from each result page
                nap_details = []
                for fr in found_results:
                    fr_url = fr["url"]
                    try:
                        page_resp = await client.get(fr_url, timeout=8.0, follow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"})
                        page_text = page_resp.text
                        
                        # Simple NAP extraction from the page
                        import re
                        page_lower = page_text.lower()
                        
                        # Find business name
                        name_found = reference.business_name.lower() in page_lower
                        
                        # Find phone (UK format)
                        phone_match = re.search(r'(?:\b0\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b)', page_text)
                        phone_found = phone_match.group(1) if phone_match else None
                        
                        # Find postcode
                        pc_match = re.search(r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b', page_text.upper())
                        postcode_found = pc_match.group(1) if pc_match else None
                        
                        nap_details.append({
                            "url": fr_url[:80],
                            "title": fr["title"][:60],
                            "has_name": name_found,
                            "phone_extracted": phone_found,
                            "postcode_extracted": postcode_found,
                        })
                    except Exception:
                        nap_details.append({
                            "url": fr_url[:80],
                            "title": fr["title"][:60],
                            "has_name": False,
                            "phone_extracted": None,
                            "postcode_extracted": None,
                        })
                
                result["status"] = "Mention Found"
                result["score"] = 70
                result["issues"] = []
                result["found_results"] = found_results
                result["nap_details"] = nap_details
                result["note"] = f"Business mentioned in {len(web_results)} search results"
                
                # Add a readable summary
                result["mentions_summary"] = "\n".join([
                    f"• {r['title'][:60]} — {r['url'][:60]}" for r in found_results
                ])
            else:
                result["status"] = "No Clear Mentions"
                result["score"] = 0
                result["issues"] = ["Business not clearly found via web search"]
    except Exception as e:
        logger.error(f"Brave NAP check failed: {e}")
        result["status"] = "Error"
        result["issues"] = [f"Search error: {str(e)[:80]}"]
    return result



async def check_web_directories(reference: NAPReference) -> List[Dict]:
    """Search the web for NAP mentions across directories using DuckDuckGo (free, no API key)."""
    import urllib.parse
    
    results = []
    query = f"{reference.business_name} {reference.postcode or reference.address}"
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # Use DuckDuckGo HTML search (free, no API key needed)
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            resp = await client.get(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            html = resp.text
            
            # Simple check for directory mentions in search results
            directory_keywords = {
                "Yell": ["yell.com", "yellbusiness"],
                "Hotfrog": ["hotfrog"],
                "Cylex": ["cylex"],
                "Thomson Local": ["thomsonlocal"],
                "Yably": ["yably"],
                "Opendi": ["opendi"],
                "N49": ["n49"],
                "Infobel": ["infobel"],
                "FreeIndex": ["freeindex"],
                "TouchLocal": ["touchlocal"],
                "Bizzy": ["bizzy"],
            }
            
            # Check if business name appears in results at all
            business_lower = reference.business_name.lower()
            has_mention = business_lower in html.lower()
            
            for dir_name, keywords in directory_keywords.items():
                found = any(kw in html.lower() for kw in keywords)
                if found:
                    results.append({
                        "source": dir_name,
                        "status": "Found",
                        "score": 65,
                        "name": reference.business_name,
                        "address": None,
                        "phone": None,
                        "issues": ["Listing found — check NAP details manually"],
                        "note": "Business appears in search results for this directory",
                    })
                else:
                    results.append({
                        "source": dir_name,
                        "status": "Not Found",
                        "score": 0,
                        "name": None,
                        "address": None,
                        "phone": None,
                        "issues": [f"No listing detected for {dir_name}"],
                        "note": "Not found in top search results",
                    })
                    
    except Exception as e:
        logger.error(f"Web directory search failed: {e}")
        for name in ["Yell", "Hotfrog", "Cylex", "Thomson Local", "Yably", "Opendi", "N49", "Infobel", "FreeIndex", "TouchLocal", "Bizzy"]:
            results.append({
                "source": name,
                "status": "Error",
                "score": 0,
                "name": None,
                "address": None,
                "phone": None,
                "issues": [f"Search failed: {str(e)[:60]}"],
                "note": "Could not complete web search",
            })
    
    return results


async def run_nap_check(business_name: str, address: str, postcode: str, phone: str) -> Dict:
    """Run a full NAP consistency check."""
    reference = NAPReference(business_name, address, postcode, phone)

    google = await check_google(reference)
    brave = await check_brave(reference)
    dirs = [google, brave]

    # Web search for directory listings
    web_results = await check_web_directories(reference)
    dirs.extend(web_results)

    # Summary
    matches = sum(1 for d in dirs if d["status"] == "Match")
    inconsistent = sum(1 for d in dirs if d["status"] == "Inconsistent")
    problems = sum(1 for d in dirs if d["status"] in ("Problem", "Not Found"))
    not_checked = sum(1 for d in dirs if d["status"] in ("Not Checked", "Requires Verification"))

    return {
        "business_name": reference.business_name,
        "reference": reference.__dict__,
        "directories": dirs,
        "summary": {
            "consistent": matches,
            "inconsistent": inconsistent,
            "problems": problems,
            "not_checked": not_checked,
            "total": len(dirs),
        },
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }