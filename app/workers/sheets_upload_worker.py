"""Celery beat task: poll yt-factory Sheets for READY_UPLOAD jobs and upload to YouTube."""
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="contentflow.poll_sheets_and_upload",
    bind=True,
    max_retries=0,
)
def poll_and_upload_task(self) -> dict:
    """Poll yt-factory Sheets for the next READY_UPLOAD job and upload it.

    Designed to run on a Celery beat schedule (default every 5 minutes).
    Processes one job per invocation to keep each run short.

    Required env vars:
        YT_FACTORY_SHEET_ID   - Google Sheets document ID
        YT_UPLOAD_ACCOUNT_ID  - Supabase social_accounts ID for YouTube
        YT_UPLOAD_OWNER_ID    - Owner ID for the YouTube account
    """
    settings = get_settings()

    sheet_id = settings.yt_factory_sheet_id
    if not sheet_id:
        return {"skipped": True, "reason": "YT_FACTORY_SHEET_ID not configured"}

    account_id = settings.yt_upload_account_id
    if not account_id:
        return {"skipped": True, "reason": "YT_UPLOAD_ACCOUNT_ID not configured"}

    owner_id = settings.yt_upload_owner_id
    if not owner_id:
        return {"skipped": True, "reason": "YT_UPLOAD_OWNER_ID not configured"}

    return asyncio.run(
        _poll_and_upload(sheet_id, account_id, owner_id),
    )


async def _poll_and_upload(
    sheet_id: str,
    account_id: str,
    owner_id: str,
) -> dict:
    """Async core: find next job, mark UPLOADING, upload, handle result."""
    from app.services.sheets_to_youtube_uploader import SheetsToYoutubeUploader

    uploader = SheetsToYoutubeUploader(
        sheet_id=sheet_id,
        youtube_account_id=account_id,
        owner_id=owner_id,
    )

    job = uploader.find_next_job()
    if not job:
        logger.info("sheets_poll_no_jobs")
        return {"skipped": True, "reason": "no READY_UPLOAD jobs"}

    job_id = job["job_id"]
    logger.info("sheets_poll_found_job", job_id=job_id)

    # Mark as UPLOADING to prevent duplicate picks
    try:
        uploader.sheets.update_job_fields(
            sheet_id, job_id, {"status": "UPLOADING"},
        )
    except Exception as exc:
        logger.error("sheets_mark_uploading_failed", job_id=job_id, error=str(exc))
        return {"success": False, "job_id": job_id, "error": f"Failed to mark UPLOADING: {exc}"}

    result = await uploader.upload_job(job)

    if not result.success:
        # Revert status so the job can be retried later
        try:
            uploader.sheets.update_job_fields(
                sheet_id, job_id, {"status": "READY_UPLOAD"},
            )
        except Exception:
            logger.error("sheets_revert_status_failed", job_id=job_id)

    return {
        "success": result.success,
        "job_id": result.job_id,
        "youtube_url": result.youtube_url,
        "youtube_video_id": result.youtube_video_id,
        "error": result.error,
    }
