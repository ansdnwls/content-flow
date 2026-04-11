"""Tests for Sheets-based YouTube upload orchestrator."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sheets_to_youtube_uploader import (
    SheetsToYoutubeUploader,
    UploadResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uploader(
    *,
    mock_sheets: MagicMock | None = None,
    mock_drive: MagicMock | None = None,
) -> SheetsToYoutubeUploader:
    """Create an uploader with mocked Sheets and Drive clients."""
    with patch(
        "app.services.sheets_to_youtube_uploader.GoogleSheetsClient",
    ) as sheets_cls, patch(
        "app.services.sheets_to_youtube_uploader.GoogleDriveClient",
    ) as drive_cls:
        sheets_cls.return_value = mock_sheets or MagicMock()
        drive_cls.return_value = mock_drive or MagicMock()
        uploader = SheetsToYoutubeUploader(
            sheet_id="sheet-123",
            youtube_account_id="acct-456",
            owner_id="owner-789",
        )
    return uploader


def _sample_job(
    *,
    job_id: str = "job-001",
    status: str = "READY_UPLOAD",
    drive_file_id: str = "drive-abc",
    thumb_file_id: str | None = "thumb-xyz",
    title: str = "My Video Title",
    description: str = "Video description",
    tags: str = "tag1, tag2, tag3",
) -> dict:
    return {
        "job_id": job_id,
        "status": status,
        "drive_file_id": drive_file_id,
        "thumb_file_id": thumb_file_id,
        "title": title,
        "description": description,
        "tags": tags,
    }


# ---------------------------------------------------------------------------
# find_next_job
# ---------------------------------------------------------------------------

class TestFindNextJob:
    """Test job discovery from Sheets."""

    def test_returns_first_ready_job(self):
        mock_sheets = MagicMock()
        mock_sheets.read_jobs_by_status.return_value = [
            _sample_job(job_id="j1"),
            _sample_job(job_id="j2"),
        ]
        uploader = _make_uploader(mock_sheets=mock_sheets)

        result = uploader.find_next_job()

        assert result is not None
        assert result["job_id"] == "j1"
        mock_sheets.read_jobs_by_status.assert_called_once_with("sheet-123", "READY_UPLOAD")

    def test_returns_none_when_no_jobs(self):
        mock_sheets = MagicMock()
        mock_sheets.read_jobs_by_status.return_value = []
        uploader = _make_uploader(mock_sheets=mock_sheets)

        result = uploader.find_next_job()

        assert result is None


# ---------------------------------------------------------------------------
# upload_job
# ---------------------------------------------------------------------------

class TestUploadJob:
    """Test the full upload orchestration."""

    @pytest.mark.asyncio
    async def test_no_drive_file_id(self):
        uploader = _make_uploader()
        job = _sample_job(drive_file_id=None)

        result = await uploader.upload_job(job)

        assert not result.success
        assert "No drive_file_id" in result.error

    @pytest.mark.asyncio
    async def test_drive_download_failure(self):
        from app.services.google_drive import DriveError

        mock_drive = MagicMock()
        mock_drive.download_file.side_effect = DriveError("download error")
        uploader = _make_uploader(mock_drive=mock_drive)

        result = await uploader.upload_job(_sample_job())

        assert not result.success
        assert "Drive download failed" in result.error

    @pytest.mark.asyncio
    async def test_youtube_upload_failure(self):
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = Path("/tmp/fake.mp4")
        uploader = _make_uploader(mock_drive=mock_drive)

        with patch.object(
            uploader, "_upload_to_youtube", new_callable=AsyncMock,
        ) as mock_upload:
            mock_upload.side_effect = RuntimeError("YouTube API error")

            with patch(
                "app.services.sheets_to_youtube_uploader.get_valid_credentials",
                new_callable=AsyncMock,
                return_value={"access_token": "tok"},
            ):
                result = await uploader.upload_job(_sample_job())

        assert not result.success
        assert "YouTube upload failed" in result.error

    @pytest.mark.asyncio
    async def test_success_full_flow(self):
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = Path("/tmp/fake.mp4")
        mock_sheets = MagicMock()
        uploader = _make_uploader(mock_sheets=mock_sheets, mock_drive=mock_drive)

        with patch.object(
            uploader, "_upload_to_youtube", new_callable=AsyncMock,
            return_value=("yt-video-123", "https://youtu.be/yt-video-123"),
        ), patch.object(
            uploader, "_set_thumbnail", new_callable=AsyncMock,
        ) as mock_thumb, patch(
            "app.services.sheets_to_youtube_uploader.get_valid_credentials",
            new_callable=AsyncMock,
            return_value={"access_token": "tok"},
        ):
            result = await uploader.upload_job(_sample_job())

        assert result.success
        assert result.youtube_video_id == "yt-video-123"
        assert result.youtube_url == "https://youtu.be/yt-video-123"
        mock_sheets.update_job_fields.assert_called_once()
        call_args = mock_sheets.update_job_fields.call_args
        assert call_args[0][1] == "job-001"
        updates = call_args[0][2]
        assert updates["status"] == "DONE"
        assert updates["youtube_video_id"] == "yt-video-123"
        mock_thumb.assert_called_once()

    @pytest.mark.asyncio
    async def test_sheets_update_failure_still_succeeds(self):
        """Upload succeeds even if Sheets update fails."""
        from app.services.google_sheets import GoogleSheetsError

        mock_drive = MagicMock()
        mock_drive.download_file.return_value = Path("/tmp/fake.mp4")
        mock_sheets = MagicMock()
        mock_sheets.update_job_fields.side_effect = GoogleSheetsError("API error")
        uploader = _make_uploader(mock_sheets=mock_sheets, mock_drive=mock_drive)

        with patch.object(
            uploader, "_upload_to_youtube", new_callable=AsyncMock,
            return_value=("yt-vid", "https://youtu.be/yt-vid"),
        ), patch.object(
            uploader, "_set_thumbnail", new_callable=AsyncMock,
        ), patch(
            "app.services.sheets_to_youtube_uploader.get_valid_credentials",
            new_callable=AsyncMock,
            return_value={"access_token": "tok"},
        ):
            result = await uploader.upload_job(_sample_job())

        # Upload itself succeeded — Sheets failure is non-fatal
        assert result.success
        assert result.youtube_video_id == "yt-vid"

    @pytest.mark.asyncio
    async def test_no_thumbnail_skips_set(self):
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = Path("/tmp/fake.mp4")
        mock_sheets = MagicMock()
        uploader = _make_uploader(mock_sheets=mock_sheets, mock_drive=mock_drive)

        with patch.object(
            uploader, "_upload_to_youtube", new_callable=AsyncMock,
            return_value=("yt-vid", "https://youtu.be/yt-vid"),
        ), patch.object(
            uploader, "_set_thumbnail", new_callable=AsyncMock,
        ) as mock_thumb, patch(
            "app.services.sheets_to_youtube_uploader.get_valid_credentials",
            new_callable=AsyncMock,
            return_value={"access_token": "tok"},
        ):
            result = await uploader.upload_job(_sample_job(thumb_file_id=None))

        assert result.success
        mock_thumb.assert_not_called()

    @pytest.mark.asyncio
    async def test_thumbnail_failure_non_fatal(self):
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = Path("/tmp/fake.mp4")
        mock_sheets = MagicMock()
        uploader = _make_uploader(mock_sheets=mock_sheets, mock_drive=mock_drive)

        with patch.object(
            uploader, "_upload_to_youtube", new_callable=AsyncMock,
            return_value=("yt-vid", "https://youtu.be/yt-vid"),
        ), patch.object(
            uploader, "_set_thumbnail", new_callable=AsyncMock,
            side_effect=RuntimeError("thumb error"),
        ), patch(
            "app.services.sheets_to_youtube_uploader.get_valid_credentials",
            new_callable=AsyncMock,
            return_value={"access_token": "tok"},
        ):
            result = await uploader.upload_job(_sample_job())

        assert result.success  # thumbnail failure is non-fatal


# ---------------------------------------------------------------------------
# UploadResult dataclass
# ---------------------------------------------------------------------------

class TestUploadResult:
    """Test UploadResult construction."""

    def test_success_result(self):
        r = UploadResult(
            job_id="j1",
            success=True,
            youtube_url="https://youtu.be/abc",
            youtube_video_id="abc",
        )
        assert r.success
        assert r.error is None

    def test_failure_result(self):
        r = UploadResult(job_id="j1", success=False, error="something broke")
        assert not r.success
        assert r.youtube_url is None
