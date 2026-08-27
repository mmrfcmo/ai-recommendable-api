"""AI Readiness Assessment API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models import ReadinessAssessment
from app.schemas import ReadinessAssessmentRequest, ReadinessAssessmentResponse
from app.services.readiness import calculate_readiness, MAX_SCORE
from app.services.notifications import send_assessment_notification

router = APIRouter(prefix="/api/v1/readiness", tags=["AI Readiness Assessment"])


@router.post("/assess", response_model=ReadinessAssessmentResponse, status_code=201)
async def submit_assessment(
    req: ReadinessAssessmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit an AI Readiness Assessment."""
    answers = {a.question_id: a.score for a in req.answers}
    total, grade, summary, breakdown = calculate_readiness(answers)

    assessment = ReadinessAssessment(
        email=req.email,
        business_name=req.business_name or "",
        q1_strategy=answers.get(1, 0),
        q2_people=answers.get(2, 0),
        q3_data=answers.get(3, 0),
        q4_tech=answers.get(4, 0),
        q5_governance=answers.get(5, 0),
        q6_trust=answers.get(6, 0),
        q7_adoption=answers.get(7, 0),
        total_score=total,
        grade=grade,
        summary=summary,
    )
    db.add(assessment)
    await db.flush()

    send_assessment_notification(req.email, req.business_name, total, grade)

    return ReadinessAssessmentResponse(
        success=True,
        message="Your AI Readiness Assessment is complete.",
        total_score=total,
        max_score=MAX_SCORE,
        grade=grade,
        summary=summary,
        breakdown=breakdown,
    )
