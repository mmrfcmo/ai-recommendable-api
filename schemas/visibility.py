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
