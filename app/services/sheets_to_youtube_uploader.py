"""Orchestrates YouTube upload from yt-factory Sheets data."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.adapters.youtube import YouTubeAdapter
from app.core.logging_config import get_logger
from app.oauth.token_store import get_valid_credentials
from app.services.google_drive import DriveError, GoogleDriveClient
from app.services.google_sheets import GoogleSheetsClient, GoogleSheetsError

logger = get_logger(__name__)


@dataclass(frozen=True)
class UploadResult:
    """Result of a YouTube upload attempt."""

    job_id: str
    success: bool
    youtube_url: str | None = None
    youtube_video_id: str | None = None
    error: str | None = None


class SheetsToYoutubeUploader:
    """Orchestrate: Sheets -> Drive download -> YouTube upload -> Sheets update."""

    def __init__(
        self,
        sheet_id: str,
        youtube_account_id: str,
        owner_id: str,
    ) -> None:
        self.sheet_id = sheet_id
        self.youtube_account_id = youtube_account_id
        self.owner_id = owner_id
        self.sheets = GoogleSheetsClient()
        self.drive = GoogleDriveClient()

    def find_next_job(self) -> dict[str, Any] | None:
        """Find the oldest READY_UPLOAD job from Sheets.

        Returns:
            Job dict or None if no job is available.
        """
        jobs = self.sheets.read_jobs_by_status(self.sheet_id, "READY_UPLOAD")
        if not jobs:
            return None
        return jobs[0]

    async def upload_job(self, job: dict[str, Any]) -> UploadResult:
        """Execute full upload flow for a single job.

        Steps:
            1. Download mp4 from Drive
            2. Optionally download thumbnail
            3. Upload to YouTube (private)
            4. Optionally set thumbnail
            5. Update Sheets with result
        """
        job_id = job["job_id"]
        logger.info("upload_job_start", job_id=job_id)

        drive_file_id = job.get("drive_file_id")
        if not drive_file_id:
            return UploadResult(
                job_id=job_id,
                success=False,
                error="No drive_file_id in Sheets",
            )

        with tempfile.TemporaryDirectory(prefix="contentflow_upload_") as tmp_dir:
            video_path = Path(tmp_dir) / f"{job_id}.mp4"

            # 1. Download video from Drive
            try:
                logger.info("downloading_video", job_id=job_id, drive_file_id=drive_file_id)
                self.drive.download_file(drive_file_id, video_path)
            except DriveError as exc:
                return UploadResult(
                    job_id=job_id,
                    success=False,
                    error=f"Drive download failed: {exc}",
                )

            # 2. Download thumbnail (optional)
            thumb_path: Path | None = None
            thumb_file_id = job.get("thumb_file_id")
            if thumb_file_id:
                try:
                    thumb_path = Path(tmp_dir) / f"{job_id}_thumb.jpg"
                    self.drive.download_file(thumb_file_id, thumb_path)
                except DriveError as exc:
                    logger.warning("thumb_download_failed", job_id=job_id, error=str(exc))
                    thumb_path = None

            # 3. Prepare metadata
            title = job.get("title") or f"Untitled {job_id[:8]}"
            description = job.get("description") or ""
            tags_raw = job.get("tags") or ""
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

            # 4. Upload to YouTube
            try:
                logger.info("uploading_to_youtube", job_id=job_id, title=title)
                credentials = await get_valid_credentials(
                    self.youtube_account_id,
                    self.owner_id,
                )
                youtube_video_id, youtube_url = await self._upload_to_youtube(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    credentials=credentials,
                )
            except Exception as exc:
                logger.error("youtube_upload_failed", job_id=job_id, error=str(exc))
                return UploadResult(
                    job_id=job_id,
                    success=False,
                    error=f"YouTube upload failed: {exc}",
                )

            # 5. Set thumbnail (optional, non-fatal)
            if thumb_path and youtube_video_id:
                try:
                    await self._set_thumbnail(
                        youtube_video_id, thumb_path, credentials,
                    )
                except Exception as exc:
                    logger.warning(
                        "thumbnail_set_failed",
                        job_id=job_id,
                        youtube_video_id=youtube_video_id,
                        error=str(exc),
                    )

            # 6. Update Sheets
            try:
                self.sheets.update_job_fields(
                    self.sheet_id,
                    job_id,
                    {
                        "status": "DONE",
                        "youtube_video_id": youtube_video_id,
                        "youtube_url": youtube_url,
                        "uploaded_at": datetime.now(UTC).isoformat(),
                    },
                )
            except GoogleSheetsError as exc:
                logger.error(
                    "sheets_update_failed_after_upload",
                    job_id=job_id,
                    youtube_video_id=youtube_video_id,
                    error=str(exc),
                )

            logger.info(
                "upload_job_complete",
                job_id=job_id,
                youtube_url=youtube_url,
            )
            return UploadResult(
                job_id=job_id,
                success=True,
                youtube_url=youtube_url,
                youtube_video_id=youtube_video_id,
            )

    async def _upload_to_youtube(
        self,
        *,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        credentials: dict[str, str],
    ) -> tuple[str, str]:
        """Upload video file to YouTube using resumable upload.

        Reuses the same resumable upload pattern as YouTubeAdapter.publish().

        Returns:
            Tuple of (youtube_video_id, youtube_url).
        """
        access_token = credentials["access_token"]
        snippet = {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
        }
        status_body = YouTubeAdapter._build_status({"privacy": "private"})

        video_bytes = video_path.read_bytes()

        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            # Step 1: Initiate resumable upload
            init_resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Upload-Content-Length": str(len(video_bytes)),
                    "X-Upload-Content-Type": "video/*",
                },
                json={"snippet": snippet, "status": status_body},
            )
            if init_resp.status_code != 200:
                raise RuntimeError(f"YouTube init failed ({init_resp.status_code}): {init_resp.text}")

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                raise RuntimeError("No upload URL returned from YouTube")

            # Step 2: Upload video bytes
            upload_resp = await client.put(
                upload_url,
                content=video_bytes,
                headers={"Content-Type": "video/*"},
            )

            if upload_resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"YouTube upload failed ({upload_resp.status_code}): {upload_resp.text}"
                )

            data = upload_resp.json()
            video_id = data["id"]
            return video_id, f"https://youtu.be/{video_id}"

    async def _set_thumbnail(
        self,
        video_id: str,
        thumb_path: Path,
        credentials: dict[str, str],
    ) -> None:
        """Upload a custom thumbnail for a YouTube video."""
        access_token = credentials["access_token"]
        thumb_bytes = thumb_path.read_bytes()
        suffix = thumb_path.suffix.lower()
        content_type = "image/png" if suffix == ".png" else "image/jpeg"

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                params={"videoId": video_id},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": content_type,
                },
                content=thumb_bytes,
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"Thumbnail upload failed ({resp.status_code}): {resp.text}"
                )
            logger.info("thumbnail_set_success", video_id=video_id)
