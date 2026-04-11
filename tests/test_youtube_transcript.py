"""Tests for YouTube transcript extraction service."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.youtube_transcript import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
    get_video_duration,
)


def _make_snippet(text: str, start: float, duration: float) -> SimpleNamespace:
    """Create a mock FetchedTranscriptSnippet object."""
    return SimpleNamespace(text=text, start=start, duration=duration)


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
    """Test transcript fetching with mocked API (youtube-transcript-api 1.x)."""

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_successful_fetch(self, mock_api_cls):
        # 1.x API: YouTubeTranscriptApi() 인스턴스 생성 후 .fetch() 호출
        mock_instance = MagicMock()
        mock_instance.fetch.return_value = [
            _make_snippet("Hello world", 0.0, 5.5),
            _make_snippet("This is a test", 5.5, 4.2),
        ]
        mock_api_cls.return_value = mock_instance

        result = fetch_transcript("xQR5-Nk9N6o")

        assert len(result) == 2
        assert result[0] == {"start": 0, "end": 5, "text": "Hello world"}
        assert result[1] == {"start": 5, "end": 9, "text": "This is a test"}

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_transcripts_disabled(self, mock_api_cls):
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_instance = MagicMock()
        mock_instance.fetch.side_effect = TranscriptsDisabled("test")
        mock_api_cls.return_value = mock_instance

        with pytest.raises(TranscriptError, match="disabled"):
            fetch_transcript("xQR5-Nk9N6o")

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_no_transcript_found(self, mock_api_cls):
        from youtube_transcript_api._errors import NoTranscriptFound

        mock_instance = MagicMock()
        mock_instance.fetch.side_effect = NoTranscriptFound(
            "xQR5-Nk9N6o", ["ko"], {}
        )
        mock_api_cls.return_value = mock_instance

        with pytest.raises(TranscriptError, match="No transcript found"):
            fetch_transcript("xQR5-Nk9N6o")

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_accepts_url(self, mock_api_cls):
        mock_instance = MagicMock()
        mock_instance.fetch.return_value = [
            _make_snippet("test", 0.0, 1.0),
        ]
        mock_api_cls.return_value = mock_instance

        result = fetch_transcript("https://youtu.be/xQR5-Nk9N6o")

        assert len(result) == 1
        mock_instance.fetch.assert_called_once_with(
            "xQR5-Nk9N6o",
            languages=["ko", "en"],
        )

    @patch("app.services.youtube_transcript.YouTubeTranscriptApi")
    def test_custom_languages(self, mock_api_cls):
        mock_instance = MagicMock()
        mock_instance.fetch.return_value = []
        mock_api_cls.return_value = mock_instance

        fetch_transcript("xQR5-Nk9N6o", languages=["ja", "en"])

        mock_instance.fetch.assert_called_once_with(
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