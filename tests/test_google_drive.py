"""Tests for Google Drive download client."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.google_drive import DriveError, GoogleDriveClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_with_mock_service() -> tuple[GoogleDriveClient, MagicMock]:
    """Create a GoogleDriveClient with a mocked Drive service."""
    with patch.object(GoogleDriveClient, "__init__", lambda self: None):
        client = GoogleDriveClient()
    client.service = MagicMock()
    return client, client.service


def _mock_downloader(data: bytes, *, chunks: int = 1):
    """Create a mock MediaIoBaseDownload that writes data to the target."""

    class FakeDownloader:
        def __init__(self, fh, request, chunksize=None):
            self._fh = fh
            self._chunk = 0
            self._total = chunks

        def next_chunk(self):
            self._chunk += 1
            if self._chunk >= self._total:
                self._fh.write(data)
                return MagicMock(progress=lambda: 1.0), True
            progress = self._chunk / self._total
            return MagicMock(progress=lambda p=progress: p), False

    return FakeDownloader


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------

class TestGoogleDriveClientInit:
    """Test client initialization."""

    @patch("app.services.google_drive.get_settings")
    def test_init_raises_when_no_json_path(self, mock_settings):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path=None,
        )
        with pytest.raises(DriveError, match="not configured"):
            GoogleDriveClient()

    @patch("app.services.google_drive.build")
    @patch("app.services.google_drive.service_account.Credentials.from_service_account_file")
    @patch("app.services.google_drive.get_settings")
    def test_init_success(self, mock_settings, mock_creds, mock_build):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path="/fake/sa.json",
        )
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        client = GoogleDriveClient()

        mock_creds.assert_called_once_with(
            "/fake/sa.json",
            scopes=GoogleDriveClient.SCOPES,
        )
        assert client.service is not None

    @patch("app.services.google_drive.service_account.Credentials.from_service_account_file")
    @patch("app.services.google_drive.get_settings")
    def test_init_raises_on_credential_error(self, mock_settings, mock_creds):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path="/bad/path.json",
        )
        mock_creds.side_effect = FileNotFoundError("no such file")

        with pytest.raises(DriveError, match="Failed to initialize"):
            GoogleDriveClient()


# ---------------------------------------------------------------------------
# get_file_metadata tests
# ---------------------------------------------------------------------------

class TestGetFileMetadata:
    """Test metadata fetching."""

    def test_success(self):
        client, service = _make_client_with_mock_service()
        expected = {
            "id": "abc123",
            "name": "video.mp4",
            "mimeType": "video/mp4",
            "size": "104857600",
        }
        service.files.return_value.get.return_value.execute.return_value = expected

        result = client.get_file_metadata("abc123")

        assert result == expected
        service.files.return_value.get.assert_called_once_with(
            fileId="abc123",
            fields="id, name, mimeType, size, createdTime, modifiedTime",
        )

    def test_http_error(self):
        from googleapiclient.errors import HttpError

        client, service = _make_client_with_mock_service()
        resp = MagicMock()
        resp.status = 404
        resp.reason = "Not Found"
        service.files.return_value.get.return_value.execute.side_effect = HttpError(
            resp, b"not found",
        )

        with pytest.raises(DriveError, match="Failed to fetch metadata"):
            client.get_file_metadata("bad_id")


# ---------------------------------------------------------------------------
# download_file tests
# ---------------------------------------------------------------------------

class TestDownloadFile:
    """Test file download to disk."""

    def test_success(self, tmp_path):
        client, service = _make_client_with_mock_service()
        content = b"hello drive file"
        dest = tmp_path / "subdir" / "output.txt"

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            _mock_downloader(content),
        ):
            result = client.download_file("file123", dest)

        assert result == dest
        assert dest.exists()
        assert dest.read_bytes() == content

    def test_creates_parent_directories(self, tmp_path):
        client, service = _make_client_with_mock_service()
        dest = tmp_path / "a" / "b" / "c" / "file.bin"

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            _mock_downloader(b"data"),
        ):
            client.download_file("file123", dest)

        assert dest.parent.exists()

    def test_deletes_partial_file_on_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        client, service = _make_client_with_mock_service()
        dest = tmp_path / "partial.mp4"
        # Pre-create a file to simulate partial download
        dest.write_bytes(b"partial data")

        resp = MagicMock()
        resp.status = 500
        resp.reason = "Server Error"

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            side_effect=HttpError(resp, b"server error"),
        ):
            with pytest.raises(DriveError, match="Download failed"):
                client.download_file("file123", dest)

        assert not dest.exists()


# ---------------------------------------------------------------------------
# download_to_bytes tests
# ---------------------------------------------------------------------------

class TestDownloadToBytes:
    """Test in-memory download."""

    def test_success(self):
        client, service = _make_client_with_mock_service()
        content = b"srt file content here"

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            _mock_downloader(content),
        ):
            result = client.download_to_bytes("srt_file_id")

        assert result == content


# ---------------------------------------------------------------------------
# download_text tests
# ---------------------------------------------------------------------------

class TestDownloadText:
    """Test text file download."""

    def test_utf8_korean(self):
        client, service = _make_client_with_mock_service()
        korean_text = "안녕하세요 자막입니다"
        content = korean_text.encode("utf-8")

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            _mock_downloader(content),
        ):
            result = client.download_text("korean_file_id")

        assert result == korean_text

    def test_bad_encoding_raises(self):
        client, service = _make_client_with_mock_service()
        # Bytes that are not valid UTF-8
        content = b"\xff\xfe\x00\x01"

        with patch(
            "app.services.google_drive.MediaIoBaseDownload",
            _mock_downloader(content),
        ):
            with pytest.raises(UnicodeDecodeError):
                client.download_text("bad_encoding_file")
