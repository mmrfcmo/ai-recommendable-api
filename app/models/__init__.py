"""AI-Recommendable models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, JSON, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DiscoverabilityReport(Base):
    """Discoverability Assessment - lead capture and scan results."""
    __tablename__ = "discoverability_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)

    score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(50), nullable=True)
    scan_results: Mapped[dict] = mapped_column(JSON, default=dict)
    report_content: Mapped[str] = mapped_column(Text, nullable=True)
    report_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReadinessAssessment(Base):
    """AI Readiness Assessment - self-serve quiz results."""
    __tablename__ = "readiness_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=True)

    q1_strategy: Mapped[int] = mapped_column(Integer, default=0)
    q2_people: Mapped[int] = mapped_column(Integer, default=0)
    q3_data: Mapped[int] = mapped_column(Integer, default=0)
    q4_tech: Mapped[int] = mapped_column(Integer, default=0)
    q5_governance: Mapped[int] = mapped_column(Integer, default=0)
    q6_trust: Mapped[int] = mapped_column(Integer, default=0)
    q7_adoption: Mapped[int] = mapped_column(Integer, default=0)

    total_score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(50), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Booking(Base):
    """Consultation booking requests."""
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    report_id: Mapped[str] = mapped_column(String(36), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
