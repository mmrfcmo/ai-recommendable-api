"""Discoverability assessment API routes."""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import DiscoverabilityReport
from app.schemas.discoverability import DiscoverabilityReportRequest, DiscoverabilityReportResponse
from app.services.trust_scanner import scan_trust_signals, TRUST_SIGNALS
from app.services.notifications import send_report_notification

router = APIRouter(prefix="/api/v1/discoverability", tags=["AI Discoverability Assessment"])


@router.post("/report", response_model=DiscoverabilityReportResponse, status_code=201)
async def create_discoverability_report(
    req: DiscoverabilityReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a Discoverability Assessment for a business."""
    website = req.website.strip()
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    # Run the scan
    signals, passed_count = await scan_trust_signals(website)
    total_score = sum(s.score for s in signals)
    total_max = sum(s.max_score for s in signals)
    percentage = round((total_score / total_max) * 100) if total_max > 0 else 0

    if percentage >= 80:
        grade = "Strong"
    elif percentage >= 60:
        grade = "Good"
    elif percentage >= 40:
        grade = "Fair"
    elif percentage >= 20:
        grade = "Weak"
    else:
        grade = "Critical"

    # Create the report record
    report = DiscoverabilityReport(
        business_name=req.business_name,
        website=website,
        email=req.email,
        phone=req.phone or "",
        score=percentage,
        grade=grade,
        scan_results={"signals": [s.dict() for s in signals], "passed": passed_count, "total": len(TRUST_SIGNALS)},
        report_generated=False,
    )
    db.add(report)
    await db.flush()

    # Send notification
    send_report_notification(req.business_name, req.email, percentage, grade, f"/report/{report.id}")

    return DiscoverabilityReportResponse(
        success=True,
        message="Your Discoverability Assessment is ready.",
        report_id=report.id,
        score=percentage,
        grade=grade,
        signals=signals,
        signals_passed=passed_count,
        signals_total=len(TRUST_SIGNALS),
        report_url=f"/report/{report.id}",
    )
