"""Tests for YouTube transcript extraction service."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.youtube_transcript import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
    get_video_duration,
)


class TestExtractVideoId:
    """Test video ID extraction from various URL formats."""

    def test_plain_video_id(self):
        assert extract_video_id("xQR5-Nk9N6o") == "xQR5-Nk9N6o"

    def test_youtube_com_watch(self):
        url = "https://www.youtube.com/watch?v=xQR5-Nk9N6o"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_youtu_be_short(self):
        url = "https://youtu.be/xQR5-Nk9N6o"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_youtu_be_with_si_param(self):
        url = "https://youtu.be/xQR5-Nk9N6o?si=abc123"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_youtube_shorts(self):
        url = "https://www.youtube.com/shorts/xQR5-Nk9N6o"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_youtube_embed(self):
        url = "https://www.youtube.com/embed/xQR5-Nk9N6o"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_mobile_youtube(self):
        url = "https://m.youtube.com/watch?v=xQR5-Nk9N6o"
        assert extract_video_id(url) == "xQR5-Nk9N6o"

    def test_invalid_url_raises(self):
        with pytest.raises(TranscriptError):
            extract_video_id("not-a-valid-url")

    def test_empty_string_raises(self):
        with pytest.raises(TranscriptError):
            extract_video_id("")


class TestFetchTranscript:
    """Test transcript fetching with mocked API."""

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_successful_fetch(self, mock_api):
        mock_api.get_transcript.return_value = [
            {"start": 0.0, "duration": 5.5, "text": "Hello world"},
            {"start": 5.5, "duration": 4.2, "text": "This is a test"},
        ]

        result = fetch_transcript("xQR5-Nk9N6o")

        assert len(result) == 2
        assert result[0] == {"start": 0, "end": 5, "text": "Hello world"}
        assert result[1] == {"start": 5, "end": 9, "text": "This is a test"}

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_transcripts_disabled(self, mock_api):
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api.get_transcript.side_effect = TranscriptsDisabled("test_id")

        with pytest.raises(TranscriptError, match="disabled"):
            fetch_transcript("xQR5-Nk9N6o")

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_no_transcript_found(self, mock_api):
        from youtube_transcript_api._errors import NoTranscriptFound

        mock_api.get_transcript.side_effect = NoTranscriptFound(
            "xQR5-Nk9N6o", ["ko"], {}
        )

        with pytest.raises(TranscriptError, match="No transcript found"):
            fetch_transcript("xQR5-Nk9N6o")

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_accepts_url(self, mock_api):
        mock_api.get_transcript.return_value = [
            {"start": 0.0, "duration": 1.0, "text": "test"},
        ]

        result = fetch_transcript("https://youtu.be/xQR5-Nk9N6o")

        assert len(result) == 1
        mock_api.get_transcript.assert_called_once_with(
            "xQR5-Nk9N6o",
            languages=["ko", "en"],
        )

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_custom_languages(self, mock_api):
        mock_api.get_transcript.return_value = []

        fetch_transcript("xQR5-Nk9N6o", languages=["ja", "en"])

        mock_api.get_transcript.assert_called_once_with(
            "xQR5-Nk9N6o",
            languages=["ja", "en"],
        )


class TestGetVideoDuration:
    """Test duration calculation from transcript."""

    def test_empty_transcript(self):
        assert get_video_duration([]) == 0

    def test_single_segment(self):
        transcript = [{"start": 0, "end": 10, "text": "hi"}]
        assert get_video_duration(transcript) == 10

    def test_multiple_segments(self):
        transcript = [
            {"start": 0, "end": 10, "text": "a"},
            {"start": 10, "end": 25, "text": "b"},
            {"start": 25, "end": 42, "text": "c"},
        ]
        assert get_video_duration(transcript) == 42
