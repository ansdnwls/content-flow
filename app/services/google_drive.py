"""Google Drive API client for downloading yt-factory files."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DriveError(Exception):
    """Raised when Google Drive operations fail."""

    pass


class GoogleDriveClient:
    """Client for downloading files from Google Drive (read-only)."""

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.google_service_account_json_path:
            raise DriveError("GOOGLE_SERVICE_ACCOUNT_JSON_PATH not configured")

        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_service_account_json_path,
                scopes=self.SCOPES,
            )
            self.service = build("drive", "v3", credentials=credentials)
            logger.info(
                "google_drive_auth_file",
                path=settings.google_service_account_json_path,
            )
        except Exception as exc:
            raise DriveError(f"Failed to initialize Drive client: {exc}") from exc

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """
        Fetch file metadata (name, size, mime_type, etc).

        Args:
            file_id: Google Drive file ID

        Returns:
            Dict with keys: id, name, mimeType, size, createdTime, modifiedTime

        Raises:
            DriveError: If file not found or permission denied
        """
        try:
            logger.info("drive_metadata_fetch_start", file_id=file_id)
            metadata = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, createdTime, modifiedTime",
            ).execute()
            logger.info(
                "drive_metadata_fetch_success",
                file_id=file_id,
                name=metadata.get("name"),
                size=metadata.get("size"),
            )
            return metadata
        except HttpError as exc:
            logger.error(
                "drive_metadata_fetch_failed",
                file_id=file_id,
                error=str(exc),
            )
            raise DriveError(f"Failed to fetch metadata: {exc}") from exc

    def download_file(
        self,
        file_id: str,
        destination_path: str | Path,
        chunk_size: int = 10 * 1024 * 1024,  # 10MB chunks
    ) -> Path:
        """
        Download a file from Google Drive to local path.

        Args:
            file_id: Google Drive file ID
            destination_path: Local path to save (will be created if not exists)
            chunk_size: Download chunk size in bytes (default 10MB)

        Returns:
            Path object of the downloaded file

        Raises:
            DriveError: If download fails
        """
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info("drive_download_start", file_id=file_id, dest=str(dest))

            request = self.service.files().get_media(fileId=file_id)

            with dest.open("wb") as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=chunk_size)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        logger.info(
                            "drive_download_progress",
                            file_id=file_id,
                            progress_pct=progress,
                        )

            size = dest.stat().st_size
            logger.info(
                "drive_download_success",
                file_id=file_id,
                dest=str(dest),
                size_bytes=size,
            )
            return dest

        except HttpError as exc:
            logger.error("drive_download_failed", file_id=file_id, error=str(exc))
            # 실패 시 불완전한 파일 삭제
            if dest.exists():
                dest.unlink()
            raise DriveError(f"Download failed: {exc}") from exc

    def download_to_bytes(self, file_id: str) -> bytes:
        """
        Download a file to memory (bytes).

        Useful for small files like SRT/JSON.
        For large files (mp4), use download_file() to disk.

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes
        """
        try:
            logger.info("drive_download_memory_start", file_id=file_id)
            request = self.service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            data = buffer.getvalue()
            logger.info(
                "drive_download_memory_success",
                file_id=file_id,
                size_bytes=len(data),
            )
            return data
        except HttpError as exc:
            logger.error(
                "drive_download_memory_failed",
                file_id=file_id,
                error=str(exc),
            )
            raise DriveError(f"Memory download failed: {exc}") from exc

    def download_text(self, file_id: str, encoding: str = "utf-8") -> str:
        """
        Download a text file (like SRT, JSON) as string.

        Args:
            file_id: Google Drive file ID
            encoding: Text encoding (default utf-8)

        Returns:
            File content as string
        """
        data = self.download_to_bytes(file_id)
        return data.decode(encoding)
