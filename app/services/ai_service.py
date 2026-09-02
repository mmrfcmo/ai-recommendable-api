"""AI Content Service - Uses OpenAI to generate high-quality, contextual deliverables."""
import os
import logging
from typing import Optional, List
from app.core.config import settings

logger = logging.getLogger("ai_recommendable.ai_service")


def _has_openai() -> bool:
    """Lazy check for OpenAI API key."""
    return bool(settings.openai_api_key)


async def generate_with_ai(prompt: str, system_message: str = None, max_tokens: int = 1000) -> Optional[str]:
    """Generate content using OpenAI."""
    if not _has_openai():
        logger.warning("OpenAI API key not configured — using templates")
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI generation failed: {e}")
        return None


async def generate_homepage_content(business_name: str, website: str, signals: list) -> Optional[str]:
    """Generate professional homepage copy based on scan results."""
    passed = [s for s in signals if getattr(s, "passed", False)]
    failed = [s for s in signals if not getattr(s, "passed", False)]

    signals_summary = []
    for s in signals:
        status = "✅ Strong" if getattr(s, "passed", False) else "❌ Needs improvement"
        signals_summary.append(f"- {s.name}: {status} (score {getattr(s, 'score', 0)}/{getattr(s, 'max_score', 0)})")

    prompt = f"""You are a copywriter specialising in AI discoverability. Write professional homepage copy for {business_name} ({website}).

Their AI Discoverability Assessment scored {len(passed)}/6 trust signals passing.

The results:
{chr(10).join(signals_summary)}

Write 4 short sections:
1. Hero headline and subheading (positioning them as a trusted authority)
2. Value proposition (2-3 sentences on what makes them trustworthy)
3. Social proof / trust signals (mentioning their strengths from the scan)
4. Call to action

Write in HTML format using <h2>, <p>, and <a> tags. Keep it professional, not salesy.
Max 300 words total."""

    system = "You are an expert copywriter who writes clear, trustworthy, conversion-focused website copy."

    return await generate_with_ai(prompt, system, max_tokens=800)


async def generate_schema_recommendations(business_name: str, website: str, industry: str = None) -> dict:
    """Generate business-specific schema recommendations."""
    prompt = f"""For {business_name} ({website}), suggest the most important Schema.org types to implement.

Industry: {industry or "Not specified"}

Provide:
1. The primary schema type (e.g. LocalBusiness, MedicalBusiness, ProfessionalService)
2. 3-5 specific properties that would be most valuable for this business type
3. Any industry-specific schema types that would help with AI discoverability

Format as a concise list."""

    system = "You are a structured data expert specialising in Schema.org markup and AI discoverability."

    result = await generate_with_ai(prompt, system, max_tokens=500)
    return result


async def generate_trust_signal_strategy(business_name: str, website: str, signals: list) -> Optional[str]:
    """Generate a specific trust signal improvement strategy."""
    prompt = f"""Create a concrete trust signal improvement plan for {business_name} ({website}).

Based on their AI discoverability scan, they need to improve in these areas:
{chr(10).join([f"- {s.name}: {getattr(s, 'details', '')}" for s in signals if not getattr(s, 'passed', False)])}

For each weak area, provide:
1. One specific, actionable step they can take this week
2. One medium-term strategy (next 30 days)
3. Expected impact on their AI discoverability

Keep it practical and specific to their business type. Max 400 words."""

    system = "You are a digital strategy consultant specialising in AI discoverability and trust signals."

    return await generate_with_ai(prompt, system, max_tokens=600)


async def generate_content_depth_strategy(business_name: str, website: str, signals: list) -> Optional[str]:
    """Generate content strategy recommendations."""
    content_signal = None
    for s in signals:
        if s.name == "content_depth":
            content_signal = s
            break

    if content_signal and getattr(content_signal, "passed", False):
        return None  # Already strong — no AI strategy needed

    prompt = f"""Create a content strategy for {business_name} ({website}) to improve their AI discoverability.

Their content depth assessment shows room for improvement. Recommend:
1. 3 specific topics they should create content about
2. Content formats that work well for AI discoverability (FAQs, guides, etc.)
3. A simple 30-day content plan

Keep it actionable and specific. Max 300 words."""

    system = "You are a content strategist specialising in AI-optimised content."

    return await generate_with_ai(prompt, system, max_tokens=500)


async def enhance_all_deliverables(business_name: str, website: str, signals: list) -> dict:
    """Generate AI-enhanced versions of all deliverables."""
    return {
        "homepage_content": await generate_homepage_content(business_name, website, signals),
        "schema_strategy": await generate_schema_recommendations(business_name, website),
        "trust_strategy": await generate_trust_signal_strategy(business_name, website, signals),
        "content_strategy": await generate_content_depth_strategy(business_name, website, signals),
    }