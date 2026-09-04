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
    """Check NAP against Google Places API (free tier)."""
    key = settings.google_places_api_key
    if not key:
        return {"source": "Google Business Profile", "status": "Not Checked", "score": 0,
                "issues": ["Google Places API key not configured"]}

    result = {"source": "Google Business Profile", "status": "Not Found", "score": 0,
              "name": None, "address": None, "phone": None, "issues": [], "note": "via Google Places API"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            # Find place
            find_resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={
                    "input": reference.business_name,
                    "inputtype": "textquery",
                    "fields": "place_id,formatted_address,name",
                    "key": key,
                },
            )
            find_data = find_resp.json()
            candidates = find_data.get("candidates") or []
            if not candidates:
                result["status"] = "Not Found"
                return result
            place_id = candidates[0]["place_id"]

            # Details
            detail_resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": place_id,
                    "fields": "name,formatted_address,formatted_phone_number,international_phone_number",
                    "key": key,
                },
            )
            d = detail_resp.json().get("result") or {}
            listing_name = d.get("name", "")
            listing_address = d.get("formatted_address", "")
            listing_phone = d.get("formatted_phone_number") or d.get("international_phone_number") or ""
            result.update(name=listing_name, address=listing_address, phone=listing_phone)
            result.update(reference.compare(listing_name, listing_address, listing_phone))
    except Exception as e:
        logger.error(f"Google NAP check failed: {e}")
        result["status"] = "Error"
        result["issues"] = [f"Google check error: {str(e)[:80]}"]
    return result



async def check_brave(reference: NAPReference) -> Dict:
    """Check NAP via Brave Search (free API, broad web coverage)."""
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
            mentions = [r.get("title", "") + " " + (r.get("description") or "") for r in web_results]
            combined = " ".join(mentions).lower()
            has_name = reference.business_name.lower() in combined
            if has_name:
                result["status"] = "Mention Found"
                result["score"] = 70
                result["issues"] = []
                result["note"] = f"Business mentioned in {len(web_results)} search results — manual directory review recommended"
            else:
                result["status"] = "No Clear Mentions"
                result["score"] = 0
                result["issues"] = ["Business not clearly found via web search"]
    except Exception as e:
        logger.error(f"Brave NAP check failed: {e}")
        result["status"] = "Error"
        result["issues"] = [f"Search error: {str(e)[:80]}"]
    return result


async def run_nap_check(business_name: str, address: str, postcode: str, phone: str) -> Dict:
    """Run a full NAP consistency check."""
    reference = NAPReference(business_name, address, postcode, phone)

    google = await check_google(reference)
    brave = await check_brave(reference)
    dirs = [google, brave]

    # Long-tail directories — always returned as unverified
    LONG_TAIL = [
        "Thomson Local", "Hotfrog", "Cylex",
        "Yably", "Opendi", "Infobel", "N49",
    ]
    for name in LONG_TAIL:
        dirs.append({
            "source": name,
            "status": "Requires Verification",
            "score": 0,
            "name": None,
            "address": None,
            "phone": None,
            "issues": ["Manual verification recommended"],
            "note": "Check this directory manually for NAP consistency",
        })

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