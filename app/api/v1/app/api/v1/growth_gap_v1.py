Growth Gap Analyst — V1
The Doctor Approach™
Takes AI-Recommendable scanner output and produces a structured diagnosis.
No AI. No dashboards. No PDFs. Just evidence → diagnosis.

Usage:
    POST /api/v1/growth-gap-diagnosis
    
    Body: {
        "website": "https://example.com",
        "business_name": "Example Business"
    }
    
    Returns: {
        "primary_constraint": "Authority",
        "confidence": "High",
        "reasoning": "...",
        "evidence": [...],
        "opportunities": [...]
    }
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List

from app.services.trust_scanner import scan_trust_signals, check_google_places

logger = logging.getLogger("doctor_approach")
router = APIRouter(prefix="/api/v1", tags=["Doctor Approach"])

class GrowthGapRequest(BaseModel):
    website: str = Field(..., min_length=1, max_length=512)
    business_name: Optional[str] = None
    industry: Optional[str] = None

class GrowthGapResponse(BaseModel):
    success: bool
    diagnosis: dict = {}
    error: str = ""

def assess_drivers(scan_signals: list, gbp_data: dict) -> dict:
    signals = {}
    for s in scan_signals:
        signals[s.name] = s
    
    def get(name):
        return signals.get(name)
    
    gbp = gbp_data or {}
    review_count = gbp.get("reviews_count", 0)
    rating = gbp.get("rating", 0)
    
    drivers = {}
    
    # VISIBILITY
    vis_score = 0
    vis_max = 100
    vis_evidence = []
    
    gbp_found = gbp.get("found", False)
    if gbp_found:
        vis_score += 30
        vis_evidence.append(f"Google Business Profile found: {gbp.get('name', '')}")
    else:
        vis_evidence.append("No Google Business Profile detected")
    
    schema = get("schema_org")
    if schema and schema.score > 0:
        vis_score += 25
        vis_evidence.append(f"Schema markup: {schema.score}/20")
    else:
        vis_evidence.append("No valid schema markup detected")
    
    nap = get("nap_consistency")
    if nap and nap.score >= 10:
        vis_score += 25
        vis_evidence.append("NAP consistency is strong")
    elif nap:
        vis_score += 10
        vis_evidence.append(f"NAP consistency: {nap.score}/15")
    
    tech = get("technical_seo")
    if tech and tech.score >= 12:
        vis_score += 20
        vis_evidence.append("Technical SEO is strong")
    elif tech:
        vis_score += 10
        vis_evidence.append(f"Technical SEO: {tech.score}/15")
    
    drivers["visibility"] = {
        "score": min(vis_score, vis_max),
        "band": _score_to_band(vis_score),
        "evidence": vis_evidence[:5]
    }
    
    # TRUST
    trust_score = 0
    trust_max = 100
    trust_evidence = []
    
    if review_count > 200:
        trust_score += 30
        trust_evidence.append(f"{review_count} Google reviews — strong social proof")
    elif review_count > 50:
        trust_score += 20
        trust_evidence.append(f"{review_count} Google reviews")
    elif review_count > 10:
        trust_score += 10
        trust_evidence.append(f"{review_count} Google reviews")
    
    if rating >= 4.5:
        trust_score += 20
        trust_evidence.append(f"Rating: {rating}/5 — excellent")
    elif rating >= 4.0:
        trust_score += 10
        trust_evidence.append(f"Rating: {rating}/5")
    
    ts = get("trust_signals")
    if ts:
        trust_score += ts.score
        if ts.score >= 10:
            trust_evidence.append(f"On-site trust signals: {ts.score}/15")
        else:
            trust_evidence.append(f"Limited on-site trust assets ({ts.score}/15)")
    
    entity = get("entity_clarity")
    if entity and entity.score >= 10:
        trust_score += 10
        trust_evidence.append("Entity clarity is strong")
    
    drivers["trust"] = {
        "score": min(trust_score, trust_max),
        "band": _score_to_band(trust_score),
        "evidence": trust_evidence[:5]
    }
    
    # AUTHORITY
    auth_score = 0
    auth_max = 100
    auth_evidence = []
    
    content = get("content_depth")
    if content:
        auth_score += content.score
        auth_evidence.append(f"Content depth: {content.score}/20")
    
    if entity and entity.score >= 8:
        auth_score += 15
        auth_evidence.append("Entity clarity suggests expertise signals exist")
    
    auth_evidence.append("Service page depth: not directly assessed")
    
    drivers["authority"] = {
        "score": min(auth_score, auth_max),
        "band": _score_to_band(auth_score),
        "evidence": auth_evidence[:5]
    }
    
    # CONVERSION
    drivers["conversion"] = {
        "score": None,
        "band": "Insufficient evidence",
        "evidence": ["Conversion signals (booking, chat, forms) were not assessed in this scan"]
    }
    
    return drivers

def identify_primary_constraint(drivers: dict) -> dict:
    candidates = []
    for name, d in drivers.items():
        if d["band"] == "Insufficient evidence":
            continue
        candidates.append({
            "driver": name,
            "score": d["score"],
            "band": d["band"]
        })
    
    if not candidates:
        return {
            "driver": "Insufficient evidence",
            "confidence": "Low",
            "reasoning": "Insufficient data to identify a primary constraint."
        }
    
    candidates.sort(key=lambda c: c["score"])
    primary = candidates[0]
    
    trust = drivers.get("trust", {})
    if primary["driver"] == "trust":
        has_trust_evidence = any(
            "reviews" in e.lower() for e in trust.get("evidence", [])
        )
        if has_trust_evidence and len(candidates) > 1:
            primary = candidates[1]
            return {
                "driver": primary["driver"],
                "confidence": "Medium",
                "reasoning": (
                    f"Although on-site trust signals are limited, the business has "
                    f"substantial evidence of actual trust through its review profile. "
                    f"The real constraint appears to be {primary['driver']}."
                )
            }
    
    if primary["driver"] == "authority":
        content_evidence = [
            e for e in drivers["authority"].get("evidence", [])
            if "content" in e.lower()
        ]
        content_detail = content_evidence[0] if content_evidence else "Limited content depth"
        return {
            "driver": primary["driver"],
            "confidence": "High",
            "reasoning": (
                f"{content_detail}. Based on available evidence, this is likely "
                f"constraining growth more than other factors."
            )
        }
    
    return {
        "driver": primary["driver"],
        "confidence": "Medium",
        "reasoning": (
            f"The weakest growth driver is {primary['driver']} "
            f"({primary['band']}, {primary['score']}/100). "
            f"Based on available evidence, this appears to be the most likely constraint."
        )
    }

def build_opportunities(primary_driver: str) -> list:
    opportunities = {
        "visibility": [
            {"title": "Claim and optimise Google Business Profile", "benefit": "Foundational for local search visibility", "priority": "High", "effort": "Low"},
            {"title": "Implement structured data markup", "benefit": "Helps search engines understand your business", "priority": "High", "effort": "Low"},
            {"title": "Build local citations across directories", "benefit": "Improves local search ranking", "priority": "Medium", "effort": "Medium"}
        ],
        "trust": [
            {"title": "Display patient testimonials on website", "benefit": "Social proof where prospects research you", "priority": "High", "effort": "Low"},
            {"title": "Implement systematic review generation", "benefit": "Builds review volume over time", "priority": "High", "effort": "Low"},
            {"title": "Add case studies or before/after galleries", "benefit": "Visual proof of outcomes", "priority": "Medium", "effort": "Medium"}
        ],
        "authority": [
            {"title": "Create detailed service/treatment pages", "benefit": "Gives search engines specific content to index", "priority": "High", "effort": "Medium"},
            {"title": "Develop a content calendar (blog, guides, FAQs)", "benefit": "Demonstrates ongoing expertise", "priority": "High", "effort": "Medium"},
            {"title": "Add practitioner profiles with credentials", "benefit": "Builds individual authority", "priority": "Medium", "effort": "Low"}
        ],
        "conversion": [
            {"title": "Add online booking or scheduling", "benefit": "Reduces friction for prospects", "priority": "High", "effort": "Medium"},
            {"title": "Implement live chat or chatbot", "benefit": "Captures visitors with questions", "priority": "High", "effort": "Low"},
            {"title": "Add lead capture forms on key pages", "benefit": "Collects contact info for follow-up", "priority": "Medium", "effort": "Low"}
        ]
    }
    return opportunities.get(primary_driver, [])

def generate_diagnosis(scan_signals: list, gbp_data: dict, business_name: str = None) -> dict:
    drivers = assess_drivers(scan_signals, gbp_data)
    primary = identify_primary_constraint(drivers)
    opportunities = build_opportunities(primary["driver"])
    
    differential = []
    for name, d in drivers.items():
        if name == primary["driver"]:
            differential.append({"candidate": name.capitalize(), "selected": True, "reason": primary["reasoning"]})
        elif d["band"] == "Insufficient evidence":
            differential.append({"candidate": name.capitalize(), "selected": False, "reason": "Insufficient evidence to assess"})
        elif d["band"] in ("Strong", "Established"):
            differential.append({"candidate": name.capitalize(), "selected": False, "reason": f"Scored {d['band']} ({d['score']}/100) — not the weakest driver"})
        else:
            differential.append({"candidate": name.capitalize(), "selected": False, "reason": f"Weaker than {primary['driver']} but not identified as primary constraint"})
    
    not_recommended = []
    for name, d in drivers.items():
        if name != primary["driver"] and d["band"] in ("Strong", "Established"):
            not_recommended.append({
                "recommendation": f"Major investment in {name}",
                "reason": f"{name.capitalize()} is already assessed as {d['band']}. Further investment likely has lower impact than addressing the primary constraint."
            })
    
    return {
        "business_name": business_name or "Unknown",
        "drivers": drivers,
        "primary_constraint": {
            "driver": primary["driver"].capitalize(),
            "confidence": primary["confidence"],
            "reasoning": primary["reasoning"]
        },
        "differential_diagnosis": differential,
        "what_we_deliberately_did_not_recommend": not_recommended[:3],
        "opportunities": opportunities,
        "next_steps": "Book a Growth Gap Review to discuss these findings and determine next steps."
    }

def _score_to_band(score: int) -> str:
    if score is None:
        return "Insufficient evidence"
    if score >= 80:
        return "Strong"
    elif score >= 60:
        return "Established"
    elif score >= 40:
        return "Developing"
    elif score >= 20:
        return "Limited"
    else:
        return "Minimal"

@router.post("/growth-gap-diagnosis", response_model=GrowthGapResponse)
async def create_growth_gap_diagnosis(req: GrowthGapRequest):
    website = req.website.strip()
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    
    business_name = req.business_name or ""
    
    try:
        logger.info(f"Scanning {website} for Growth Gap Diagnosis")
        signals, passed_count = await scan_trust_signals(website, business_name)
        gbp_data = await check_google_places(business_name or website)
        name = business_name or gbp_data.get("name", website)
        diagnosis = generate_diagnosis(signals, gbp_data, name)
        return GrowthGapResponse(success=True, diagnosis=diagnosis)
    except Exception as e:
        logger.error(f"Growth Gap Diagnosis failed: {e}", exc_info=True)
