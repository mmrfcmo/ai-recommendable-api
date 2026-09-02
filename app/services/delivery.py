"""Client Delivery Report - Generates PDF-ready deliverables from completed tasks."""
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.workflow_db import Project, Task, TaskStatus, TaskType
from app.core.database import async_session_factory

logger = logging.getLogger("ai_recommendable.delivery")


def _signal_label(signal_name: str) -> str:
    """Convert internal signal names to human-readable labels."""
    labels = {
        "schema_org": "Schema.org Markup",
        "nap_consistency": "NAP Consistency",
        "entity_clarity": "Entity Clarity",
        "content_depth": "Content Depth",
        "trust_signals": "Trust Signals",
        "technical_seo": "Technical SEO",
    }
    return labels.get(signal_name, signal_name.replace("_", " ").title())


def _task_label(task_type: str) -> str:
    """Convert task types to human-readable labels."""
    labels = {
        "content_generation": "Website Content",
        "report_generation": "Discoverability Report",
        "seo_audit": "SEO Audit",
        "schema_markup": "Schema.org Markup",
        "citation_building": "Citation Building",
        "google_business_optimisation": "Google Business Profile",
        "social_media_setup": "Social Media Setup",
    }
    return labels.get(task_type, task_type.replace("_", " ").title())


def build_delivery_markdown(project, tasks: list) -> str:
    """Build a markdown delivery report from project and task data."""
    score = project.discoverability_score
    grade = project.discoverability_grade

    lines = [
        f"# Discoverability Report — {project.business_name}",
        f"",
        f"**Website:** {project.website}",
        f"**Score:** {score}/100 ({grade})",
        f"**Generated:** {datetime.now().strftime('%d %B %Y')}",
        f"",
        "---",
        f"",
        f"## Executive Summary",
        f"",
        f"{project.business_name} scored **{score}/100** ({grade}) for AI discoverability. "
        f"This report details the findings and provides actionable deliverables to improve "
        f"how your business appears to AI systems.",
        f"",
        "---",
        f"",
        f"## Deliverables",
        f"",
    ]

    # Group tasks by signal relevance
    task_map = {}
    for t in tasks:
        task_type = t.type.value if hasattr(t.type, "value") else t.type
        task_map[task_type] = t

    def add_task_section(task_type, title):
        t = task_map.get(task_type)
        if not t:
            return

        lines.append(f"### {title}")
        lines.append(f"")
        lines.append(f"**Status:** {getattr(t.status, 'value', t.status)}")
        lines.append(f"")

        output = t.output or {}
        if output.get("generated"):
            if task_type == "seo_audit":
                lines.append("**SEO Audit Findings:**")
                findings = output.get("findings", [])
                for f_item in findings:
                    icon = "✅" if f_item.get("status") == "passed" else "❌"
                    detail = f_item.get("detail", "")
                    rec = f_item.get("recommendation", "")
                    if rec:
                        lines.append(f"- {icon} {detail} → **{rec}**")
                    else:
                        lines.append(f"- {icon} {detail}")
                passed = output.get("passed", 0)
                failed = output.get("failed", 0)
                lines.append(f"")
                lines.append(f"**{passed} of {passed + failed} signals passing.**")
                lines.append(f"")

            elif task_type == "schema_markup":
                if output.get("status") == "existing":
                    lines.append(f"✅ Schema.org markup already detected.")
                    lines.append(f"")
                else:
                    lines.append(f"❌ No schema.org markup detected.")
                    lines.append(f"")
                    lines.append(f"**Recommended Schema (JSON-LD):**")
                    lines.append(f"")
                    lines.append(f"```json")
                    lines.append(f'{{')
                    lines.append(f'  "@context": "https://schema.org",')
                    lines.append(f'  "@type": "LocalBusiness",')
                    lines.append(f'  "name": "{project.business_name}",')
                    lines.append(f'  "url": "{project.website}"')
                    lines.append(f'}}')
                    lines.append(f"```")
                    lines.append(f"")
                    lines.append(f"**Additional recommendations:**")
                    for rec in output.get("recommendations", []):
                        lines.append(f"- {rec}")
                    lines.append(f"")

            elif task_type == "citation_building":
                if output.get("status") == "has_contact_info":
                    lines.append(f"✅ NAP information found on website.")
                else:
                    lines.append(f"❌ No consistent NAP information found.")
                lines.append(f"")
                lines.append(f"**Recommended directories:**")
                for d in output.get("directories", []):
                    lines.append(f"- {d}")
                lines.append(f"")

            elif task_type == "content_generation":
                content = output.get("content", "")
                if content:
                    lines.append(f"**Generated content:**")
                    lines.append(f"")
                    # Strip HTML for markdown view
                    import re
                    text = re.sub(r'<[^>]+>', '', content)
                    lines.append(text)
                    lines.append(f"")
                    lines.append(f"**Word count:** {output.get('word_count', 0)}")
                    lines.append(f"**Sections:** {', '.join(output.get('sections', []))}")
                    lines.append(f"")

            elif task_type == "report_generation":
                summary = output.get("summary", "")
                if summary:
                    lines.append(f"**Summary:** {summary}")
                    lines.append(f"")
                    lines.append(f"**Signal Breakdown:**")
                    for sig in output.get("signal_breakdown", []):
                        icon = "✅" if sig.get("passed") else "❌"
                        lines.append(f"- {icon} **{sig.get('name')}** — {sig.get('score')}/{sig.get('max_score')} — {sig.get('details')}")
                    lines.append(f"")

            else:
                # Generic output display
                for key, val in output.items():
                    if key not in ("generated", "task_type", "generated_at"):
                        lines.append(f"- **{key.replace('_', ' ').title()}:** {val}")
                lines.append(f"")
        else:
            error = output.get("error", "Not yet generated")
            lines.append(f"⚠️ {error}")
            lines.append(f"")

    # Order: SEO audit first (foundational), then schema, citations, content, report
    add_task_section("seo_audit", "1. SEO Audit")
    lines.append("---")
    add_task_section("schema_markup", "2. Schema.org Markup")
    lines.append("---")
    add_task_section("citation_building", "3. Citation Building")
    lines.append("---")
    add_task_section("content_generation", "4. Website Content")
    lines.append("---")
    add_task_section("report_generation", "5. Discoverability Summary")
    lines.append("---")

    # Trust signal recap
    lines.extend([
        f"## Trust Signal Scorecard",
        f"",
        f"| Signal | Status | Score |",
        f"|--------|--------|-------|",
    ])

    scan_results = project.scan_results or {}
    signals = scan_results.get("signals", [])
    for s in signals:
        name = s.get("name", "")
        passed = s.get("passed", False)
        score = s.get("score", 0)
        max_score = s.get("max_score", 0)
        icon = "✅" if passed else "❌"
        lines.append(f"| {_signal_label(name)} | {icon} | {score}/{max_score} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Next Steps",
        f"",
        f"1. **Review** each deliverable above",
        f"2. **Approve or request revisions** via your project dashboard",
        f"3. **Deploy** schema markup and content to your website",
        f"4. **Re-scan** in 30 days to see your improved score",
        f"",
        f"---",
        f"",
        f"*Generated by AI-Recommendable — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*",
    ])

    return "\n".join(lines)


async def generate_project_delivery(project_id: str) -> str:
    """Generate delivery markdown for a project."""
    async with async_session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        tasks_result = await db.execute(
            select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
        )
        tasks = tasks_result.scalars().all()

    return build_delivery_markdown(project, tasks)