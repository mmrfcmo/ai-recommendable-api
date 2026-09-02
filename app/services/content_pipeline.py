"""Discoverability Content Pipeline - Generates deliverables from scan data."""
import logging
from datetime import datetime

logger = logging.getLogger("ai_recommendable.content_pipeline")

GENERATORS = {}


def register_generator(name):
    def decorator(func):
        GENERATORS[name] = func
        return func
    return decorator


@register_generator("content_generation")
async def generate_content(task, project, scan_data, signals):
    """Generate homepage copy based on scan findings."""
    # Build content from weak signals
    weak_signals = [s for s in signals if not getattr(s, "passed", False)]
    strong_signals = [s for s in signals if getattr(s, "passed", False)]

    sections = []

    # Hero section
    sections.append(f"<h2>Welcome to {project.business_name}</h2>")

    # Value proposition based on strong signals
    if strong_signals:
        sections.append("<p>We're proud of our strong online presence. "
                        "Our customers trust us — and it shows.</p>")

    # Improvement areas
    if weak_signals:
        sections.append("<h2>Areas We're Improving</h2>")
        items = []
        for s in weak_signals[:3]:
            items.append(f"<li>Enhancing our {s.details[:60]}</li>")
        sections.append("<ul>" + "".join(items) + "</ul>")

    # CTA
    sections.append("<h2>Ready to Get Started?</h2>")
    sections.append("<p>Contact us today for a free discoverability consultation.</p>")

    content = "\n".join(sections)
    return {
        "content": content,
        "word_count": len(content.split()),
        "sections": ["hero", "value_proposition", "improvement_areas", "cta"],
        "generated": True,
    }


@register_generator("report_generation")
async def generate_report(task, project, scan_data, signals):
    """Generate a summary report from scan results."""
    passed = sum(1 for s in signals if getattr(s, "passed", False))
    total = len(signals)
    score = project.discoverability_score
    grade = project.discoverability_grade

    report = {
        "business_name": project.business_name,
        "website": project.website,
        "score": score,
        "grade": grade,
        "summary": f"{project.business_name} scored {score}/100 ({grade}) "
                   f"with {passed}/{total} trust signals passing.",
        "signal_breakdown": [
            {
                "name": s.name,
                "passed": getattr(s, "passed", False),
                "score": getattr(s, "score", 0),
                "max_score": getattr(s, "max_score", 0),
                "details": getattr(s, "details", ""),
            }
            for s in signals
        ],
        "generated": True,
        "generated_at": datetime.now().isoformat(),
    }
    return report


@register_generator("seo_audit")
async def generate_seo_audit(task, project, scan_data, signals):
    """Generate SEO audit findings from scan data."""
    findings = []
    for s in signals:
        if not getattr(s, "passed", False):
            findings.append({
                "signal": s.name,
                "status": "failed",
                "detail": getattr(s, "details", ""),
                "recommendation": f"Improve {s.name.replace('_', ' ')}",
            })
        else:
            findings.append({
                "signal": s.name,
                "status": "passed",
                "detail": getattr(s, "details", ""),
            })
    return {
        "findings": findings,
        "total_signals": len(signals),
        "passed": sum(1 for s in signals if getattr(s, "passed", False)),
        "failed": sum(1 for s in signals if not getattr(s, "passed", False)),
        "generated": True,
    }


@register_generator("schema_markup")
async def generate_schema_recommendations(task, project, scan_data, signals):
    """Generate schema.org markup recommendations."""
    schema_signal = None
    for s in signals:
        if s.name == "schema_org":
            schema_signal = s
            break

    if schema_signal and getattr(schema_signal, "passed", False):
        score = getattr(schema_signal, "score", 0)
        max_score = getattr(schema_signal, "max_score", 20)
        
        if score >= max_score:
            return {
                "status": "complete",
                "detail": "Schema.org markup detected and well-implemented",
                "recommendations": ["Consider adding Product schema", "Add FAQ schema if applicable"],
                "generated": True,
            }
        else:
            # Schema exists but is incomplete — provide specific improvements
            return {
                "status": "partial",
                "detail": "Schema.org markup found but incomplete. Missing LocalBusiness schema with business details.",
                "json_ld": {
                    "@context": "https://schema.org",
                    "@type": "LocalBusiness",
                    "name": "{{business_name}}",
                    "url": "{{website}}",
                    "telephone": "{{phone}}",
                    "email": "{{email}}",
                    "address": {
                        "@type": "PostalAddress"
                    },
                    "aggregateRating": {
                        "@type": "AggregateRating",
                        "ratingValue": "",
                        "reviewCount": ""
                    },
                    "openingHoursSpecification": [
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Monday", "opens": "09:00", "closes": "17:00"},
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Tuesday", "opens": "09:00", "closes": "17:00"},
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Wednesday", "opens": "09:00", "closes": "17:00"},
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Thursday", "opens": "09:00", "closes": "17:00"},
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Friday", "opens": "09:00", "closes": "17:00"}
                    ],
                    "sameAs": []
                },
                "recommendations": [
                    "Add LocalBusiness schema with full business details (name, address, phone, opening hours)",
                    "Add AggregateRating schema to display star ratings in search results",
                    "Add FAQ schema using your existing FAQ content",
                    "Add breadcrumb schema for better navigation understanding",
                    "Link your Google Business Profile via sameAs array",
                ],
                "generated": True,
            }
    else:
        return {
            "status": "needs_implementation",
            "detail": "No schema.org markup detected",
            "json_ld": {
                "@context": "https://schema.org",
                "@type": "LocalBusiness",
                "name": "{{business_name}}",
                "url": "{{website}}",
                "telephone": "{{phone}}",
                "email": "{{email}}",
                "address": {
                    "@type": "PostalAddress"
                },
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": "",
                    "reviewCount": ""
                },
                "openingHoursSpecification": [
                    {"@type": "OpeningHoursSpecification", "dayOfWeek": "Monday", "opens": "09:00", "closes": "17:00"},
                    {"@type": "OpeningHoursSpecification", "dayOfWeek": "Tuesday", "opens": "09:00", "closes": "17:00"},
                    {"@type": "OpeningHoursSpecification", "dayOfWeek": "Wednesday", "opens": "09:00", "closes": "17:00"},
                    {"@type": "OpeningHoursSpecification", "dayOfWeek": "Thursday", "opens": "09:00", "closes": "17:00"},
                    {"@type": "OpeningHoursSpecification", "dayOfWeek": "Friday", "opens": "09:00", "closes": "17:00"}
                ],
                "sameAs": []
            },
            "recommendations": [
                "Add LocalBusiness schema with full business details (name, address, phone, opening hours)",
                "Add Organization schema for company-level information",
                "Implement FAQ schema for common questions",
                "Add breadcrumb schema for better navigation understanding",
                "Add AggregateRating schema to display star ratings in search results",
            ],
            "generated": True,
        }


@register_generator("citation_building")
async def generate_citations(task, project, scan_data, signals):
    """Generate citation building recommendations."""
    nap_signal = None
    for s in signals:
        if s.name == "nap_consistency":
            nap_signal = s
            break

    if nap_signal and getattr(nap_signal, "passed", False):
        return {
            "status": "has_contact_info",
            "detail": "NAP information found on website",
            "directories": [
                "Google Business Profile", "Yelp", "Bing Places",
                "Apple Maps", "Facebook Business",
            ],
            "generated": True,
        }
    else:
        return {
            "status": "needs_implementation",
            "detail": "No consistent NAP information found",
            "recommendations": [
                "Add business name, address, and phone to website footer",
                "Create consistent NAP across all directories",
                "Set up Google Business Profile",
            ],
            "generated": True,
        }


async def run_generator(task, project, signals):
    """Run content generator for a task."""
    task_type = task.type.value if hasattr(task.type, "value") else task.type
    if task_type not in GENERATORS:
        return {"error": f"No generator for {task_type}", "generated": False}

    scan_data = {}
    try:
        output = await GENERATORS[task_type](task, project, scan_data, signals)
        output["task_type"] = task_type
        output["generated_at"] = datetime.now().isoformat()
        return output
    except Exception as e:
        return {"error": str(e), "generated": False}