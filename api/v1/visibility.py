"""AI Visibility Report API routes."""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import VisibilityReport
from app.schemas.visibility import VisibilityReportRequest, VisibilityReportResponse
from app.services.visibility_scanner import scan_visibility, AI_SIGNALS
from app.services.notifications import send_report_notification

router = APIRouter(prefix="/api/v1/visibility", tags=["AI Visibility Report"])


@router.post("/report", response_model=VisibilityReportResponse, status_code=201)
async def create_visibility_report(
    req: VisibilityReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an AI Visibility Report for a business."""
    website = req.website.strip()
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    # Run the scan
    signals, passed_count = await scan_visibility(website)
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
    report = VisibilityReport(
        business_name=req.business_name,
        website=website,
        email=req.email,
        phone=req.phone or "",
        score=percentage,
        grade=grade,
        scan_results={"signals": [s.dict() for s in signals], "passed": passed_count, "total": len(AI_SIGNALS)},
        report_generated=False,
    )
    db.add(report)
    await db.flush()

    # Send notification
    send_report_notification(req.business_name, req.email, percentage, grade, f"/report/{report.id}")

    return VisibilityReportResponse(
        success=True,
        message="Your AI Visibility Report is ready.",
        report_id=report.id,
        score=percentage,
        grade=grade,
        signals=signals,
        signals_passed=passed_count,
        signals_total=len(AI_SIGNALS),
        report_url=f"/report/{report.id}",
    )
