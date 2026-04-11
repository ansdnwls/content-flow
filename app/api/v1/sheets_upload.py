"""API endpoints for Sheets-based YouTube upload."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.config import get_settings
from app.services.sheets_to_youtube_uploader import (
    SheetsToYoutubeUploader,
)

router = APIRouter(prefix="/sheets", tags=["sheets"])

CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class NextJobResponse(BaseModel):
    found: bool
    job_id: str | None = None
    title: str | None = None
    drive_file_id: str | None = None


class UploadResponse(BaseModel):
    success: bool
    job_id: str
    youtube_url: str | None = None
    youtube_video_id: str | None = None
    error: str | None = None


@router.get("/next-job", response_model=NextJobResponse)
async def get_next_job(user: CurrentUser) -> NextJobResponse:
    """Find the next READY_UPLOAD job from yt-factory Sheets."""
    settings = get_settings()
    sheet_id = settings.yt_factory_sheet_id
    if not sheet_id:
        raise HTTPException(400, "YT_FACTORY_SHEET_ID not configured")

    uploader = SheetsToYoutubeUploader(
        sheet_id=sheet_id,
        youtube_account_id="",
        owner_id=user.id,
    )

    job = uploader.find_next_job(job_id=body.job_id)
    if not job:
        return NextJobResponse(found=False)

    return NextJobResponse(
        found=True,
        job_id=job["job_id"],
        title=job.get("title"),
        drive_file_id=job.get("drive_file_id"),
    )


class UploadNextRequest(BaseModel):
    youtube_account_id: str
    job_id: str | None = None


@router.post("/upload-next", response_model=UploadResponse)
async def upload_next_job(
    body: UploadNextRequest,
    user: CurrentUser,
) -> UploadResponse:
    """Pick the next READY_UPLOAD job and upload it to YouTube."""
    settings = get_settings()
    sheet_id = settings.yt_factory_sheet_id
    if not sheet_id:
        raise HTTPException(400, "YT_FACTORY_SHEET_ID not configured")

    uploader = SheetsToYoutubeUploader(
        sheet_id=sheet_id,
        youtube_account_id=body.youtube_account_id,
        owner_id=user.id,
    )

    job = uploader.find_next_job(job_id=body.job_id)
    if not job:
        raise HTTPException(404, "No READY_UPLOAD jobs")

    result = await uploader.upload_job(job)

    return UploadResponse(
        success=result.success,
        job_id=result.job_id,
        youtube_url=result.youtube_url,
        youtube_video_id=result.youtube_video_id,
        error=result.error,
    )


