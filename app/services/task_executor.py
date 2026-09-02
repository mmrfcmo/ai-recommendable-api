"""Task Executor - Runs content generators for fulfilment tasks automatically."""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.workflow_db import Task, TaskStatus, TaskType, Project
from app.services.content_pipeline import run_generator

logger = logging.getLogger("ai_recommendable.task_executor")


async def execute_task(task_id: str, project_id: str, signals: list) -> dict:
    """Execute a single task by running its content generator."""
    async with async_session_factory() as db:
        try:
            result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task {task_id} not found")
                return {"error": "Task not found"}

            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                logger.error(f"Project {project_id} not found")
                return {"error": "Project not found"}

            # Mark as running
            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
            await db.flush()

            # Run the generator
            output = await run_generator(task, project, signals)

            if output.get("generated", False):
                task.status = TaskStatus.completed if task.status != TaskStatus.awaiting_review else TaskStatus.awaiting_review
                task.output = output
                task.completed_at = datetime.now(timezone.utc)
                if task.started_at:
                    task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
            else:
                task.status = TaskStatus.failed
                task.output = {"error": output.get("error", "Generation failed")}
                task.completed_at = datetime.now(timezone.utc)

            await db.commit()
            return {"task_id": task_id, "status": task.status.value, "output": output}

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            try:
                await db.rollback()
                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.failed
                    task.output = {"error": str(e)}
                    task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass
            return {"error": str(e)}


async def execute_project_tasks(project_id: str, signals: list) -> List[dict]:
    """Execute all pending tasks for a project in dependency order."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
        )
        tasks = result.scalars().all()

    results = []
    executed = set()

    # Simple topological execution — keep trying until no more can run
    remaining = list(tasks)
    while remaining:
        batch = []
        still_remaining = []

        for t in remaining:
            deps_met = all(d in executed for d in t.depends_on)
            if deps_met and t.status == TaskStatus.pending:
                batch.append(t)
            elif deps_met and t.status == TaskStatus.awaiting_review:
                # Awaiting review tasks still get generated but stay awaiting_review
                # We process them after all dependencies are done
                if all(d in executed for d in t.depends_on):
                    batch.append(t)
            else:
                still_remaining.append(t)

        if not batch:
            # Nothing left to execute — remaining tasks have unmet dependencies
            break

        for t in batch:
            result = await execute_task(t.id, project_id, signals)
            executed.add(t.id)
            results.append(result)

        remaining = still_remaining

    # Log what's left
    if remaining:
        logger.info(f"{len(remaining)} tasks skipped (dependencies not met): "
                     f"{[t.type.value for t in remaining]}")

    return results