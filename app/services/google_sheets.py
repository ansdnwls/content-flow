"""Google Sheets client using service account authentication."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsError(Exception):
    """Raised when a Google Sheets operation fails."""

    pass


class GoogleSheetsClient:
    """Google Sheets client using service account credentials.

    Authentication priority:
    1. GOOGLE_SERVICE_ACCOUNT_JSON_PATH — path to JSON key file
    2. GOOGLE_SERVICE_ACCOUNT_JSON — JSON string (for Railway / Docker)
    3. Explicit credentials passed to constructor
    """

    def __init__(self, credentials: Credentials | None = None) -> None:
        self._credentials = credentials or self._load_credentials()
        self._service = build(
            "sheets",
            "v4",
            credentials=self._credentials,
            cache_discovery=False,
        )

    @staticmethod
    def _load_credentials() -> Credentials:
        """Load service account credentials from settings."""
        settings = get_settings()

        # Priority 1: JSON key file path
        if settings.google_service_account_json_path:
            path = Path(settings.google_service_account_json_path)
            if not path.exists():
                raise GoogleSheetsError(
                    f"Service account JSON file not found: {path}"
                )
            logger.info(
                "google_sheets_auth_file",
                path=str(path),
            )
            return Credentials.from_service_account_file(
                str(path),
                scopes=_SCOPES,
            )

        # Priority 2: JSON string (env var)
        if settings.google_service_account_json:
            try:
                info = json.loads(settings.google_service_account_json)
            except json.JSONDecodeError as exc:
                raise GoogleSheetsError(
                    "Invalid GOOGLE_SERVICE_ACCOUNT_JSON: not valid JSON"
                ) from exc
            logger.info("google_sheets_auth_json_env")
            return Credentials.from_service_account_info(
                info,
                scopes=_SCOPES,
            )

        raise GoogleSheetsError(
            "No Google service account credentials configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON_PATH or GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    def read_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> list[list[str]]:
        """Read raw rows from a sheet range.

        Args:
            spreadsheet_id: The Google Sheets document ID.
            range_name: A1 notation range (e.g. "Sheet1!A1:F100" or "Sheet1").

        Returns:
            List of rows, each row a list of cell strings.

        Raises:
            GoogleSheetsError: On API or permission errors.
        """
        logger.info(
            "sheets_read_start",
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
        )
        try:
            result = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )
        except HttpError as exc:
            status = exc.resp.status if exc.resp else 0
            if status == 403:
                raise GoogleSheetsError(
                    f"Permission denied for spreadsheet {spreadsheet_id}. "
                    "Share the sheet with the service account email."
                ) from exc
            if status == 404:
                raise GoogleSheetsError(
                    f"Spreadsheet not found: {spreadsheet_id}"
                ) from exc
            raise GoogleSheetsError(
                f"Google Sheets API error ({status}): {exc}"
            ) from exc

        rows: list[list[str]] = result.get("values", [])
        logger.info(
            "sheets_read_success",
            spreadsheet_id=spreadsheet_id,
            row_count=len(rows),
        )
        return rows

    def read_sheet_as_dicts(
        self,
        spreadsheet_id: str,
        sheet_name: str = "Sheet1",
        *,
        range_suffix: str = "",
    ) -> list[dict[str, Any]]:
        """Read a sheet and return rows as dicts keyed by header row.

        The first row is treated as column headers. Empty trailing cells
        are filled with empty strings.

        Args:
            spreadsheet_id: The Google Sheets document ID.
            sheet_name: Name of the sheet tab (default "Sheet1").
            range_suffix: Optional A1 range suffix (e.g. "!A1:Z1000").

        Returns:
            List of dicts, one per data row.

        Raises:
            GoogleSheetsError: On API errors or empty sheet.
        """
        range_name = f"{sheet_name}{range_suffix}" if range_suffix else sheet_name
        rows = self.read_sheet(spreadsheet_id, range_name)

        if not rows:
            return []

        headers = rows[0]
        if not headers:
            raise GoogleSheetsError("Sheet has no header row")

        result: list[dict[str, Any]] = []
        for row in rows[1:]:
            # Pad short rows with empty strings
            padded = row + [""] * (len(headers) - len(row))
            result.append(dict(zip(headers, padded, strict=False)))

        return result

    # ------------------------------------------------------------------
    # yt-factory Queue helpers
    # ------------------------------------------------------------------

    YT_FACTORY_COL_MAP: dict[str, int] = {
        "job_id": 0,
        "channel_id": 1,
        "mode": 2,
        "topic_seed": 3,
        "aspect_ratio": 4,
        "script_hash": 5,
        "idempotency_key": 6,
        "status": 7,
        "title": 24,
        "description": 25,
        "tags": 26,
        "publish_at": 27,
        "drive_file_id": 31,
        "thumb_file_id": 32,
        "caption_file_id": 33,
        "youtube_video_id": 34,
        "youtube_url": 35,
        "uploaded_at": 36,
        "subtitle_ass_drive_id": 54,
    }

    def read_queue_rows(
        self,
        sheet_id: str,
        sheet_name: str = "Queue",
        *,
        start_row: int = 1,
        end_row: int = 1000,
    ) -> list[dict[str, Any]]:
        """Read yt-factory Queue sheet as a list of dicts.

        The Queue sheet has no header row — data starts at row 1.
        Column indices are mapped via ``YT_FACTORY_COL_MAP``.

        Args:
            sheet_id: Google Sheets document ID.
            sheet_name: Sheet tab name (default "Queue").
            start_row: First row to read (1-based, default 1).
            end_row: Last row to read (default 1000).

        Returns:
            List of dicts with named fields. Empty rows are skipped.
        """
        range_a1 = f"{sheet_name}!A{start_row}:BJ{end_row}"
        raw_rows = self.read_sheet(sheet_id, range_a1)

        result: list[dict[str, Any]] = []
        for row in raw_rows:
            if not row or not row[0]:
                continue
            row_dict: dict[str, Any] = {}
            for field, idx in self.YT_FACTORY_COL_MAP.items():
                row_dict[field] = row[idx] if idx < len(row) else None
            result.append(row_dict)

        return result

    def read_jobs_by_status(
        self,
        sheet_id: str,
        status: str,
        sheet_name: str = "Queue",
    ) -> list[dict[str, Any]]:
        """Filter yt-factory Queue rows by status.

        Common statuses:
        - READY_UPLOAD: video ready, awaiting distribution
        - DONE: fully distributed
        - READY_GENERATE: awaiting generation
        - GENERATING: in progress
        """
        all_rows = self.read_queue_rows(sheet_id, sheet_name)
        return [row for row in all_rows if row.get("status") == status]

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _col_letter(col: int) -> str:
        """Convert 1-based column number to letter(s). 1=A, 26=Z, 27=AA."""
        result = ""
        while col > 0:
            col, remainder = divmod(col - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def update_cell(
        self,
        sheet_id: str,
        sheet_name: str,
        row: int,
        col: int,
        value: Any,
    ) -> None:
        """Update a single cell by row/col (both 1-based).

        Args:
            sheet_id: Google Sheets document ID.
            sheet_name: Tab name (e.g. "Queue").
            row: 1-based row number.
            col: 1-based column number.
            value: Value to write.
        """
        range_a1 = f"{sheet_name}!{self._col_letter(col)}{row}"
        try:
            self._service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_a1,
                valueInputOption="USER_ENTERED",
                body={"values": [[value]]},
            ).execute()
            logger.info(
                "sheets_cell_updated",
                sheet_id=sheet_id,
                range=range_a1,
                value=str(value)[:50],
            )
        except HttpError as exc:
            logger.error(
                "sheets_cell_update_failed",
                sheet_id=sheet_id,
                range=range_a1,
                error=str(exc),
            )
            raise GoogleSheetsError(f"Failed to update cell: {exc}") from exc

    def update_job_fields(
        self,
        sheet_id: str,
        job_id: str,
        updates: dict[str, Any],
        sheet_name: str = "Queue",
    ) -> None:
        """Update multiple fields for a job identified by job_id.

        Uses ``YT_FACTORY_COL_MAP`` to locate columns.

        Args:
            sheet_id: Google Sheets document ID.
            job_id: Target job_id value in the Queue sheet.
            updates: Mapping of field_name -> new value.
            sheet_name: Tab name (default "Queue").

        Raises:
            GoogleSheetsError: If the job is not found or an API call fails.
        """
        all_rows = self.read_queue_rows(sheet_id, sheet_name)
        target_row_idx: int | None = None
        for idx, row in enumerate(all_rows):
            if row.get("job_id") == job_id:
                target_row_idx = idx + 1  # 1-based, no header row
                break

        if target_row_idx is None:
            raise GoogleSheetsError(f"Job not found: {job_id}")

        for field, value in updates.items():
            if field not in self.YT_FACTORY_COL_MAP:
                logger.warning("unknown_field_skipped", field=field)
                continue
            col_idx = self.YT_FACTORY_COL_MAP[field] + 1  # 0-based -> 1-based
            self.update_cell(sheet_id, sheet_name, target_row_idx, col_idx, value)
