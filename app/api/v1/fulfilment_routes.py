"""Fulfilment Dashboard - API routes for managing projects and tasks."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger("ai_recommendable.fulfilment")
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.workflow_db import Project, Task, TaskType, TaskStatus, ProjectStatus
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/v1/fulfilment", tags=["Fulfilment"])


class ProjectSummary(BaseModel):
    id: str
    business_name: str
    website: str
    status: str
    product_type: str
    price: float = 0.0
    discoverability_score: int = 0
    discoverability_grade: str = ""
    progress: float = 0.0
    task_count: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_awaiting_review: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    depends_on: list[str] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    output: dict = {}
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None

    class Config:
        from_attributes = True


class WorkflowDetail(BaseModel):
    project: ProjectSummary
    tasks: list[TaskSummary]


class ApprovalRequest(BaseModel):
    task_id: str
    approved: bool
    notes: str = ""


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(status_filter: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List all fulfilment projects."""
    query = select(Project)
    if status_filter:
        query = query.where(Project.status == status_filter)
    query = query.order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    output = []
    for p in projects:
        tasks_result = await db.execute(select(Task).where(Task.project_id == p.id))
        task_list = tasks_result.scalars().all()
        total = len(task_list)
        completed = sum(1 for t in task_list if t.status in (TaskStatus.completed, TaskStatus.approved, TaskStatus.skipped))
        failed = sum(1 for t in task_list if t.status == TaskStatus.failed)
        awaiting = sum(1 for t in task_list if t.status == TaskStatus.awaiting_review)

        output.append(ProjectSummary(
            id=p.id,
            business_name=p.business_name,
            website=p.website,
            status=p.status.value,
            product_type=p.product_type,
            price=p.price,
            discoverability_score=p.discoverability_score,
            discoverability_grade=p.discoverability_grade,
            progress=completed / total if total > 0 else 0.0,
            task_count=total,
            tasks_completed=completed,
            tasks_failed=failed,
            tasks_awaiting_review=awaiting,
            created_at=p.created_at,
            completed_at=p.completed_at,
        ))
    return output


@router.get("/projects/{project_id}", response_model=WorkflowDetail)
async def get_project_workflow(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get full project workflow with all tasks."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks_result = await db.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
    )
    tasks = tasks_result.scalars().all()

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status in (TaskStatus.completed, TaskStatus.approved, TaskStatus.skipped))

    task_summaries = [
        TaskSummary(
            id=t.id,
            project_id=t.project_id,
            type=t.type.value,
            status=t.status.value,
            depends_on=t.depends_on,
            created_at=t.created_at,
            started_at=t.started_at,
            completed_at=t.completed_at,
            duration_seconds=t.duration_seconds,
            retry_count=t.retry_count,
            max_retries=t.max_retries,
            output=t.output,
            reviewed_by=t.reviewed_by,
            review_notes=t.review_notes,
        )
        for t in tasks
    ]

    return WorkflowDetail(
        project=ProjectSummary(
            id=project.id,
            business_name=project.business_name,
            website=project.website,
            status=project.status.value,
            product_type=project.product_type,
            price=project.price,
            discoverability_score=project.discoverability_score,
            discoverability_grade=project.discoverability_grade,
            progress=completed / total if total > 0 else 0.0,
            task_count=total,
            tasks_completed=completed,
            tasks_failed=sum(1 for t in tasks if t.status == TaskStatus.failed),
            tasks_awaiting_review=sum(1 for t in tasks if t.status == TaskStatus.awaiting_review),
            created_at=project.created_at,
            completed_at=project.completed_at,
        ),
        tasks=task_summaries,
    )


@router.post("/tasks/approve", status_code=status.HTTP_200_OK)
async def approve_or_reject_task(req: ApprovalRequest, db: AsyncSession = Depends(get_db)):
    """Approve or reject a task."""
    result = await db.execute(select(Task).where(Task.id == req.task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = TaskStatus.approved if req.approved else TaskStatus.rejected
    task.reviewed_at = datetime.now(timezone.utc)
    task.review_notes = req.notes
    await db.commit()

    return {"success": True, "task_id": req.task_id, "new_status": task.status.value}


@router.post("/projects/{project_id}/execute", status_code=status.HTTP_200_OK)
async def execute_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger task execution for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Extract signals from scan results
    signals = []
    if project.scan_results:
        raw_signals = project.scan_results.get("signals", [])
        from app.schemas.discoverability import SignalResult
        for s in raw_signals:
            signals.append(SignalResult(
                name=s.get("name", ""),
                passed=s.get("passed", False),
                score=s.get("score", 0),
                max_score=s.get("max_score", 0),
                details=s.get("details", ""),
            ))

    import asyncio
    from app.services.task_executor import execute_project_tasks

    async def run_and_notify():
        try:
            results = await execute_project_tasks(project.id, signals)
            logger.info(f"Manual execute for {project_id}: {len(results)} tasks")
        except Exception as e:
            logger.error(f"Manual execute failed: {e}")

    asyncio.create_task(run_and_notify())

    return {"success": True, "project_id": project_id, "message": "Task execution started"}


@router.get("/projects/{project_id}/deliver")
async def deliver_project_report(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate delivery PDF for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.delivery import generate_project_delivery

    try:
        markdown = await generate_project_delivery(project_id)
        return {"success": True, "project_id": project_id, "markdown": markdown, "business_name": project.business_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/deploy")
async def deploy_to_wordpress(
    project_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Deploy completed deliverables to a WordPress site."""
    site_url = body.get("site_url")
    username = body.get("username")
    password = body.get("password")

    if not site_url or not username or not password:
        raise HTTPException(status_code=400, detail="site_url, username, and password are required")

    from app.services.wordpress_connector import deploy_project_to_wordpress

    result = await deploy_project_to_wordpress(project_id, site_url, username, password)
    return result


@router.post("/tasks/{task_id}/regenerate")
async def regenerate_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Reset a task for regeneration."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = TaskStatus.pending
    task.retry_count = 0
    task.output = {}
    task.reviewed_by = None
    task.reviewed_at = None
    await db.commit()

    return {"success": True, "task_id": task_id, "new_status": task.status.value}


@router.post("/projects/from-scan/{scan_id}", status_code=status.HTTP_201_CREATED)
async def create_project_from_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Create a fulfilment project from a completed discoverability scan."""
    from app.models import DiscoverabilityReport

    result = await db.execute(select(DiscoverabilityReport).where(DiscoverabilityReport.id == scan_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Scan report not found")

    project = Project(
        business_name=report.business_name,
        website=report.website,
        email=report.email,
        phone=report.phone or "",
        discoverability_score=report.score,
        discoverability_grade=report.grade,
        scan_results=report.scan_results or {},
        status=ProjectStatus.active,
        product_type="discoverability_improvement",
        price=995.0,
    )
    db.add(project)
    await db.flush()

    # Create initial task set
    task_definitions = [
        {"type": TaskType.seo_audit, "depends_on": []},
        {"type": TaskType.schema_markup, "depends_on": ["seo_audit"]},
        {"type": TaskType.citation_building, "depends_on": ["seo_audit"]},
        {"type": TaskType.google_business_optimisation, "depends_on": ["seo_audit"]},
        {"type": TaskType.social_media_setup, "depends_on": ["seo_audit"]},
        {"type": TaskType.report_generation, "depends_on": ["schema_markup", "citation_building"], "status": TaskStatus.awaiting_review},
        {"type": TaskType.content_generation, "depends_on": ["schema_markup", "citation_building"], "status": TaskStatus.awaiting_review},
    ]

    for td in task_definitions:
        t = Task(
            project_id=project.id,
            type=td["type"],
            depends_on=td["depends_on"],
            status=td.get("status", TaskStatus.pending),
        )
        db.add(t)

    await db.commit()

    # Extract signals from scan results for the executor
    signals = []
    if report.scan_results:
        raw_signals = report.scan_results.get("signals", [])
        from app.schemas.discoverability import SignalResult
        for s in raw_signals:
            signals.append(SignalResult(
                name=s.get("name", ""),
                passed=s.get("passed", False),
                score=s.get("score", 0),
                max_score=s.get("max_score", 0),
                details=s.get("details", ""),
            ))

    # Auto-execute tasks in background
    import asyncio
    from app.services.task_executor import execute_project_tasks

    async def run_and_notify():
        try:
            results = await execute_project_tasks(project.id, signals)
            logger.info(f"Project {project.id}: {len(results)} tasks executed")
        except Exception as e:
            logger.error(f"Project {project.id} execution failed: {e}")

    asyncio.create_task(run_and_notify())

    return {"success": True, "project_id": project.id, "tasks_created": len(task_definitions)}