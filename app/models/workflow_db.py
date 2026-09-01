"""Workflow Engine - SQLAlchemy models for project and task persistence."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum
from sqlalchemy import String, DateTime, Text, Enum as SAEnum, ForeignKey, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ProjectStatus(str, Enum):
    new = "new"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    monitoring = "monitoring"


class TaskStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    approved = "approved"
    rejected = "rejected"
    awaiting_review = "awaiting_review"


class TaskType(str, Enum):
    content_generation = "content_generation"
    report_generation = "report_generation"
    review_approval = "review_approval"
    seo_audit = "seo_audit"
    schema_markup = "schema_markup"
    citation_building = "citation_building"
    google_business_optimisation = "google_business_optimisation"
    social_media_setup = "social_media_setup"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    discoverability_score: Mapped[int] = mapped_column(Integer, default=0)
    discoverability_grade: Mapped[str] = mapped_column(String(50), nullable=True)
    scan_results: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ProjectStatus] = mapped_column(SAEnum(ProjectStatus), default=ProjectStatus.new, nullable=False)
    product_type: Mapped[str] = mapped_column(String(50), default="discoverability_improvement")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "fulfilment_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.pending, nullable=False)
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_by: Mapped[str] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)

    project = relationship("Project", back_populates="tasks")