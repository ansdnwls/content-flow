"""Tests for Google Sheets read-only client."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.google_sheets import (
    GoogleSheetsClient,
    GoogleSheetsError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_client_with_mock_service() -> tuple[GoogleSheetsClient, MagicMock]:
    """Build a GoogleSheetsClient with a mocked Sheets API service."""
    mock_creds = MagicMock()
    with patch("app.services.google_sheets.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        client = GoogleSheetsClient(credentials=mock_creds)
    return client, mock_service


def _mock_values_get(mock_service: MagicMock, return_value: dict) -> None:
    """Wire up mock_service.spreadsheets().values().get().execute()."""
    mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = return_value


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

class TestCredentialLoading:
    """Test service account credential resolution."""

    @patch("app.services.google_sheets.get_settings")
    def test_raises_when_no_credentials(self, mock_settings):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path=None,
            google_service_account_json=None,
        )
        with pytest.raises(GoogleSheetsError, match="No Google service account"):
            GoogleSheetsClient._load_credentials()

    @patch("app.services.google_sheets.get_settings")
    def test_raises_when_json_file_missing(self, mock_settings):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path="/nonexistent/path.json",
            google_service_account_json=None,
        )
        with pytest.raises(GoogleSheetsError, match="not found"):
            GoogleSheetsClient._load_credentials()

    @patch("app.services.google_sheets.get_settings")
    def test_raises_when_json_string_invalid(self, mock_settings):
        mock_settings.return_value = MagicMock(
            google_service_account_json_path=None,
            google_service_account_json="not-json",
        )
        with pytest.raises(GoogleSheetsError, match="not valid JSON"):
            GoogleSheetsClient._load_credentials()

    @patch("app.services.google_sheets.Credentials")
    @patch("app.services.google_sheets.get_settings")
    def test_loads_from_json_string(self, mock_settings, mock_creds_cls):
        sa_info = {"type": "service_account", "project_id": "test"}
        mock_settings.return_value = MagicMock(
            google_service_account_json_path=None,
            google_service_account_json=json.dumps(sa_info),
        )
        mock_creds_cls.from_service_account_info.return_value = MagicMock()

        creds = GoogleSheetsClient._load_credentials()

        mock_creds_cls.from_service_account_info.assert_called_once()
        assert creds is not None


# ---------------------------------------------------------------------------
# read_sheet
# ---------------------------------------------------------------------------

class TestReadSheet:
    """Test raw sheet reading."""

    def test_returns_rows(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                ["Name", "Status"],
                ["Video 1", "done"],
                ["Video 2", "pending"],
            ]
        })

        rows = client.read_sheet("sheet-id-123", "Sheet1")

        assert len(rows) == 3
        assert rows[0] == ["Name", "Status"]
        assert rows[1] == ["Video 1", "done"]

    def test_returns_empty_for_empty_sheet(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {})

        rows = client.read_sheet("sheet-id-123", "Sheet1")

        assert rows == []

    def test_permission_denied_raises(self):
        client, mock_service = _build_client_with_mock_service()
        from googleapiclient.errors import HttpError

        resp = MagicMock(status=403)
        error = HttpError(resp, b"Forbidden")
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = error

        with pytest.raises(GoogleSheetsError, match="Permission denied"):
            client.read_sheet("sheet-id-123", "Sheet1")

    def test_not_found_raises(self):
        client, mock_service = _build_client_with_mock_service()
        from googleapiclient.errors import HttpError

        resp = MagicMock(status=404)
        error = HttpError(resp, b"Not Found")
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = error

        with pytest.raises(GoogleSheetsError, match="not found"):
            client.read_sheet("sheet-id-123", "Sheet1")


# ---------------------------------------------------------------------------
# read_sheet_as_dicts
# ---------------------------------------------------------------------------

class TestReadSheetAsDicts:
    """Test dict-based sheet reading."""

    def test_converts_to_dicts(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                ["video_id", "title", "status"],
                ["abc123", "My Video", "done"],
                ["def456", "Another", "pending"],
            ]
        })

        result = client.read_sheet_as_dicts("sheet-id-123", "Sheet1")

        assert len(result) == 2
        assert result[0] == {"video_id": "abc123", "title": "My Video", "status": "done"}
        assert result[1] == {"video_id": "def456", "title": "Another", "status": "pending"}

    def test_pads_short_rows(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                ["col_a", "col_b", "col_c"],
                ["only_a"],
            ]
        })

        result = client.read_sheet_as_dicts("sheet-id-123")

        assert result[0] == {"col_a": "only_a", "col_b": "", "col_c": ""}

    def test_empty_sheet_returns_empty_list(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {})

        result = client.read_sheet_as_dicts("sheet-id-123")

        assert result == []

    def test_header_only_returns_empty_list(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [["col_a", "col_b"]]
        })

        result = client.read_sheet_as_dicts("sheet-id-123")

        assert result == []

    def test_empty_header_raises(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [[], ["data"]]
        })

        with pytest.raises(GoogleSheetsError, match="no header"):
            client.read_sheet_as_dicts("sheet-id-123")
