"""Worker tasks for recurring schedule execution."""

from __future__ import annotations

import asyncio

from app.services.scheduler_service import SchedulerService
from app.workers.celery_app import celery_app


async def run_due_schedules() -> dict:
    """Find and execute due recurring schedules."""
    service = SchedulerService()
    due = await service.get_due_schedules()

    executed = 0
    for schedule in due:
        # Advance to next run (or deactivate if once)
        await service.advance_schedule(schedule["id"], schedule)
        executed += 1

    return {"executed": executed, "scanned": len(due)}


@celery_app.task(name="contentflow.run_due_schedules")
def run_due_schedules_task() -> dict:
    return asyncio.run(run_due_schedules())
