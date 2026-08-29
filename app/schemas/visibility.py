"""Pydantic schemas for AI-Recommendable."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class VisibilityReportRequest(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    website: str = Field(..., min_length=1, max_length=512)
    email: EmailStr
    phone: Optional[str] = None


class ReadinessAnswer(BaseModel):
    question_id: int
    score: int = Field(..., ge=0, le=5)


class ReadinessAssessmentRequest(BaseModel):
    email: EmailStr
    business_name: Optional[str] = None
    answers: List[ReadinessAnswer]


class ReadinessAssessmentResponse(BaseModel):
    success: bool
    message: str
    total_score: int
    max_score: int
    grade: str
    summary: str
    breakdown: dict


class BookingRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    report_id: Optional[str] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str

"""Visibility report schemas."""
from pydantic import BaseModel
from typing import Optional, List


class SignalResult(BaseModel):
    name: str
    passed: bool
    score: int
    max_score: int
    details: str


class VisibilityReportResponse(BaseModel):
    success: bool
    message: str
    report_id: str = ""
    score: int = 0
    grade: str = ""
    signals: List[SignalResult] = []
    signals_passed: int = 0
    signals_total: int = 6
    report_url: str = ""
    error: str = ""
