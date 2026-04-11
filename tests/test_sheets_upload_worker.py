"""Tests for sheets_upload_worker Celery beat task."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.sheets_upload_worker import _poll_and_upload, poll_and_upload_task


# ---------------------------------------------------------------------------
# poll_and_upload_task — config guard tests (sync wrapper)
# ---------------------------------------------------------------------------

class TestPollAndUploadTask:
    """Test the synchronous Celery task entry point."""

    def test_skips_when_no_sheet_id(self):
        with patch("app.workers.sheets_upload_worker.get_settings") as mock:
            mock.return_value = MagicMock(
                yt_factory_sheet_id=None,
                yt_upload_account_id="acct",
                yt_upload_owner_id="owner",
            )
            result = poll_and_upload_task()
        assert result["skipped"] is True
        assert "SHEET_ID" in result["reason"]

    def test_skips_when_no_account_id(self):
        with patch("app.workers.sheets_upload_worker.get_settings") as mock:
            mock.return_value = MagicMock(
                yt_factory_sheet_id="sheet-1",
                yt_upload_account_id=None,
                yt_upload_owner_id="owner",
            )
            result = poll_and_upload_task()
        assert result["skipped"] is True
        assert "ACCOUNT_ID" in result["reason"]

    def test_skips_when_no_owner_id(self):
        with patch("app.workers.sheets_upload_worker.get_settings") as mock:
            mock.return_value = MagicMock(
                yt_factory_sheet_id="sheet-1",
                yt_upload_account_id="acct",
                yt_upload_owner_id=None,
            )
            result = poll_and_upload_task()
        assert result["skipped"] is True
        assert "OWNER_ID" in result["reason"]


# ---------------------------------------------------------------------------
# _poll_and_upload — async core logic
# ---------------------------------------------------------------------------

class TestPollAndUploadAsync:
    """Test the async poll-and-upload logic."""

    @pytest.mark.asyncio
    async def test_no_jobs_available(self):
        mock_uploader = MagicMock()
        mock_uploader.find_next_job.return_value = None

        with patch(
            "app.services.sheets_to_youtube_uploader.SheetsToYoutubeUploader",
            return_value=mock_uploader,
        ):
            result = await _poll_and_upload("sheet-1", "acct-1", "owner-1")

        assert result["skipped"] is True
        assert "no READY_UPLOAD" in result["reason"]

    @pytest.mark.asyncio
    async def test_successful_upload(self):
        from app.services.sheets_to_youtube_uploader import UploadResult

        mock_uploader = MagicMock()
        mock_uploader.find_next_job.return_value = {"job_id": "j-001", "drive_file_id": "d-1"}
        mock_uploader.upload_job = AsyncMock(
            return_value=UploadResult(
                job_id="j-001",
                success=True,
                youtube_url="https://youtu.be/abc",
                youtube_video_id="abc",
            ),
        )

        with patch(
            "app.services.sheets_to_youtube_uploader.SheetsToYoutubeUploader",
            return_value=mock_uploader,
        ):
            result = await _poll_and_upload("sheet-1", "acct-1", "owner-1")

        assert result["success"] is True
        assert result["youtube_url"] == "https://youtu.be/abc"
        # Verify UPLOADING was set before upload
        mock_uploader.sheets.update_job_fields.assert_called_once_with(
            "sheet-1", "j-001", {"status": "UPLOADING"},
        )

    @pytest.mark.asyncio
    async def test_failed_upload_reverts_status(self):
        from app.services.sheets_to_youtube_uploader import UploadResult

        mock_uploader = MagicMock()
        mock_uploader.find_next_job.return_value = {"job_id": "j-002", "drive_file_id": "d-2"}
        mock_uploader.upload_job = AsyncMock(
            return_value=UploadResult(
                job_id="j-002",
                success=False,
                error="Drive download failed",
            ),
        )

        with patch(
            "app.services.sheets_to_youtube_uploader.SheetsToYoutubeUploader",
            return_value=mock_uploader,
        ):
            result = await _poll_and_upload("sheet-1", "acct-1", "owner-1")

        assert result["success"] is False
        # Verify status was reverted to READY_UPLOAD
        calls = mock_uploader.sheets.update_job_fields.call_args_list
        assert len(calls) == 2
        assert calls[0][0] == ("sheet-1", "j-002", {"status": "UPLOADING"})
        assert calls[1][0] == ("sheet-1", "j-002", {"status": "READY_UPLOAD"})

    @pytest.mark.asyncio
    async def test_mark_uploading_failure(self):
        from app.services.google_sheets import GoogleSheetsError

        mock_uploader = MagicMock()
        mock_uploader.find_next_job.return_value = {"job_id": "j-003", "drive_file_id": "d-3"}
        mock_uploader.sheets.update_job_fields.side_effect = GoogleSheetsError("API error")

        with patch(
            "app.services.sheets_to_youtube_uploader.SheetsToYoutubeUploader",
            return_value=mock_uploader,
        ):
            result = await _poll_and_upload("sheet-1", "acct-1", "owner-1")

        assert result["success"] is False
        assert "UPLOADING" in result["error"]
        # upload_job should NOT have been called
        mock_uploader.upload_job.assert_not_called()


# ---------------------------------------------------------------------------
# Beat schedule registration
# ---------------------------------------------------------------------------

class TestBeatSchedule:
    """Verify the task is registered in celery_app beat_schedule."""

    def test_registered_in_beat_schedule(self):
        from app.workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        entry = schedule.get("poll-sheets-and-upload-video")
        assert entry is not None
        assert entry["task"] == "contentflow.poll_sheets_and_upload"
        assert entry["schedule"] > 0
