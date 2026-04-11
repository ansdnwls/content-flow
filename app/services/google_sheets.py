"""Google Sheets read-only client using service account authentication."""
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

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class GoogleSheetsError(Exception):
    """Raised when a Google Sheets operation fails."""

    pass


class GoogleSheetsClient:
    """Read-only Google Sheets client using service account credentials.

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
