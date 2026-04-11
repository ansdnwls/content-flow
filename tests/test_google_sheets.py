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


# ---------------------------------------------------------------------------
# yt-factory Queue helpers
# ---------------------------------------------------------------------------

def _make_queue_row(
    job_id: str = "job-001",
    status: str = "READY_UPLOAD",
    title: str = "My Video",
    drive_file_id: str = "drive-abc",
) -> list[str]:
    """Build a fake yt-factory Queue row (62 columns wide)."""
    row = [""] * 62
    col = GoogleSheetsClient.YT_FACTORY_COL_MAP
    row[col["job_id"]] = job_id
    row[col["channel_id"]] = "ch001"
    row[col["status"]] = status
    row[col["title"]] = title
    row[col["drive_file_id"]] = drive_file_id
    row[col["subtitle_ass_drive_id"]] = "ass-xyz"
    return row


class TestReadQueueRows:
    """Test yt-factory Queue sheet reading."""

    def test_maps_columns(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                _make_queue_row("job-001", "READY_UPLOAD", "Video One", "d1"),
                _make_queue_row("job-002", "DONE", "Video Two", "d2"),
            ]
        })

        result = client.read_queue_rows("sheet-id")

        assert len(result) == 2
        assert result[0]["job_id"] == "job-001"
        assert result[0]["status"] == "READY_UPLOAD"
        assert result[0]["title"] == "Video One"
        assert result[0]["drive_file_id"] == "d1"
        assert result[0]["subtitle_ass_drive_id"] == "ass-xyz"
        assert result[1]["job_id"] == "job-002"

    def test_skips_empty_rows(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                _make_queue_row("job-001"),
                [],
                [""],
                _make_queue_row("job-002"),
            ]
        })

        result = client.read_queue_rows("sheet-id")

        assert len(result) == 2
        assert result[0]["job_id"] == "job-001"
        assert result[1]["job_id"] == "job-002"

    def test_handles_short_rows(self):
        client, mock_service = _build_client_with_mock_service()
        # Row with only 10 columns (subtitle_ass_drive_id at idx 54 missing)
        short_row = ["job-short", "ch001", "", "", "", "", "", "DONE", "", ""]
        _mock_values_get(mock_service, {"values": [short_row]})

        result = client.read_queue_rows("sheet-id")

        assert len(result) == 1
        assert result[0]["job_id"] == "job-short"
        assert result[0]["status"] == "DONE"
        assert result[0]["subtitle_ass_drive_id"] is None
        assert result[0]["title"] is None

    def test_empty_sheet(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {})

        result = client.read_queue_rows("sheet-id")

        assert result == []


class TestReadJobsByStatus:
    """Test status-based filtering."""

    def test_filters_by_status(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                _make_queue_row("j1", "READY_UPLOAD"),
                _make_queue_row("j2", "DONE"),
                _make_queue_row("j3", "READY_UPLOAD"),
                _make_queue_row("j4", "GENERATING"),
            ]
        })

        result = client.read_jobs_by_status("sheet-id", "READY_UPLOAD")

        assert len(result) == 2
        assert result[0]["job_id"] == "j1"
        assert result[1]["job_id"] == "j3"

    def test_no_matches_returns_empty(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [_make_queue_row("j1", "DONE")]
        })

        result = client.read_jobs_by_status("sheet-id", "READY_UPLOAD")

        assert result == []


# ---------------------------------------------------------------------------
# _col_letter
# ---------------------------------------------------------------------------

class TestColLetter:
    """Test column number to letter conversion."""

    def test_single_letter(self):
        assert GoogleSheetsClient._col_letter(1) == "A"
        assert GoogleSheetsClient._col_letter(26) == "Z"

    def test_double_letter(self):
        assert GoogleSheetsClient._col_letter(27) == "AA"
        assert GoogleSheetsClient._col_letter(28) == "AB"
        assert GoogleSheetsClient._col_letter(52) == "AZ"
        assert GoogleSheetsClient._col_letter(53) == "BA"

    def test_triple_letter(self):
        assert GoogleSheetsClient._col_letter(703) == "AAA"


# ---------------------------------------------------------------------------
# update_cell
# ---------------------------------------------------------------------------

def _mock_values_update(mock_service: MagicMock) -> MagicMock:
    """Wire up mock for spreadsheets().values().update().execute()."""
    mock_update = MagicMock()
    mock_service.spreadsheets.return_value.values.return_value.update.return_value.execute = mock_update
    return mock_update


class TestUpdateCell:
    """Test single cell update."""

    def test_success(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_update(mock_service)

        client.update_cell("sheet-id", "Queue", 3, 8, "DONE")

        mock_service.spreadsheets.return_value.values.return_value.update.assert_called_once_with(
            spreadsheetId="sheet-id",
            range="Queue!H3",
            valueInputOption="USER_ENTERED",
            body={"values": [["DONE"]]},
        )

    def test_http_error_raises(self):
        from googleapiclient.errors import HttpError

        client, mock_service = _build_client_with_mock_service()
        resp = MagicMock(status=500)
        mock_service.spreadsheets.return_value.values.return_value.update.return_value.execute.side_effect = HttpError(
            resp, b"Server Error",
        )

        with pytest.raises(GoogleSheetsError, match="Failed to update cell"):
            client.update_cell("sheet-id", "Queue", 1, 1, "val")


# ---------------------------------------------------------------------------
# update_job_fields
# ---------------------------------------------------------------------------

class TestUpdateJobFields:
    """Test multi-field job update."""

    def test_updates_multiple_fields(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {
            "values": [
                _make_queue_row("job-001", "READY_UPLOAD"),
                _make_queue_row("job-002", "DONE"),
            ]
        })
        _mock_values_update(mock_service)

        client.update_job_fields("sheet-id", "job-001", {
            "status": "DONE",
            "youtube_video_id": "yt-abc",
        })

        calls = mock_service.spreadsheets.return_value.values.return_value.update.call_args_list
        assert len(calls) == 2

    def test_job_not_found_raises(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {"values": [_make_queue_row("job-001")]})

        with pytest.raises(GoogleSheetsError, match="Job not found"):
            client.update_job_fields("sheet-id", "nonexistent", {"status": "DONE"})

    def test_unknown_field_skipped(self):
        client, mock_service = _build_client_with_mock_service()
        _mock_values_get(mock_service, {"values": [_make_queue_row("job-001")]})
        _mock_values_update(mock_service)

        client.update_job_fields("sheet-id", "job-001", {
            "status": "DONE",
            "nonexistent_field": "ignored",
        })

        calls = mock_service.spreadsheets.return_value.values.return_value.update.call_args_list
        assert len(calls) == 1  # only status updated
