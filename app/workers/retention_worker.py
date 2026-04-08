"""Periodic retention and GDPR deletion worker."""

from __future__ import annotations

from app.services.retention_service import run_retention_jobs
from app.workers.celery_app import celery_app


@celery_app.task(name="contentflow.run_retention_policies")
def run_retention_policies() -> dict:
    """Run retention cleanup and due deletion processing."""
    return run_retention_jobs()
