"""Unit tests for YouTubeToBlogPipeline."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.youtube_to_blog import (
    PipelineOptions,
    PipelineResult,
    YouTubeToBlogPipeline,
)


# ---------------------------------------------------------------------------
# PipelineOptions
# ---------------------------------------------------------------------------


class TestPipelineOptions:
    def test_defaults(self):
        opts = PipelineOptions()
        assert opts.blog_id is None
        assert opts.extra_tags == []
        assert opts.generate_images is True
        assert opts.max_transcript_chars == 4000

    def test_custom_values(self):
        opts = PipelineOptions(
            blog_id="test_blog",
            extra_tags=["a", "b"],
            generate_images=False,
            max_transcript_chars=2000,
        )
        assert opts.blog_id == "test_blog"
        assert opts.extra_tags == ["a", "b"]
        assert opts.generate_images is False
        assert opts.max_transcript_chars == 2000

    def test_frozen(self):
        opts = PipelineOptions()
        with pytest.raises(AttributeError):
            opts.blog_id = "changed"


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------


class TestPipelineResult:
    def test_success_result(self):
        result = PipelineResult(
            success=True,
            video_id="abc123",
            title="Test Title",
            tags=["t1"],
            blocks=[{"type": "paragraph", "text": "hello"}],
            blog_url="https://blog.naver.com/test/123",
        )
        assert result.success is True
        assert result.video_id == "abc123"
        assert result.blog_url == "https://blog.naver.com/test/123"
        assert result.error == ""

    def test_error_result(self):
        result = PipelineResult(
            success=False,
            video_id="abc123",
            error="Transcript failed",
        )
        assert result.success is False
        assert result.error == "Transcript failed"
        assert result.title == ""
        assert result.blocks == []


# ---------------------------------------------------------------------------
# YouTubeToBlogPipeline
# ---------------------------------------------------------------------------


class TestYouTubeToBlogPipeline:
    """Mock-based tests for pipeline error handling."""

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        pipeline = YouTubeToBlogPipeline()
        result = await pipeline.run("")
        assert result.success is False
        assert "Empty URL or ID" in result.error

    @pytest.mark.asyncio
    @patch("app.services.youtube_to_blog.fetch_transcript")
    @patch("app.services.youtube_to_blog.extract_video_id", return_value="test123")
    async def test_transcript_failure(self, mock_vid, mock_fetch):
        from app.services.youtube_transcript import TranscriptError

        mock_fetch.side_effect = TranscriptError("Transcripts disabled")

        pipeline = YouTubeToBlogPipeline()
        result = await pipeline.run("https://youtube.com/watch?v=test123")

        assert result.success is False
        assert "Transcripts disabled" in result.error

    @pytest.mark.asyncio
    @patch("app.services.youtube_to_blog.NaverBlogPlaywright")
    @patch("app.services.youtube_to_blog.fetch_transcript")
    @patch("app.services.youtube_to_blog.extract_video_id", return_value="test123")
    async def test_claude_failure(self, mock_vid, mock_fetch, mock_naver):
        mock_fetch.return_value = [
            {"start": 0, "end": 5, "text": "hello world"},
        ]

        pipeline = YouTubeToBlogPipeline(PipelineOptions(generate_images=False))

        with patch.object(
            pipeline,
            "convert_to_blog",
            side_effect=RuntimeError("API error"),
        ):
            result = await pipeline.run("https://youtube.com/watch?v=test123")

        assert result.success is False
        assert "Claude conversion failed (RuntimeError)" in result.error

    @pytest.mark.asyncio
    @patch("app.services.youtube_to_blog.NaverBlogPlaywright")
    @patch("app.services.youtube_to_blog.fetch_transcript")
    @patch("app.services.youtube_to_blog.extract_video_id", return_value="test123")
    async def test_no_session_returns_content(self, mock_vid, mock_fetch, mock_naver_cls):
        mock_fetch.return_value = [
            {"start": 0, "end": 5, "text": "hello"},
        ]

        mock_naver = MagicMock()
        mock_naver.has_session.return_value = False
        mock_naver_cls.return_value = mock_naver

        pipeline = YouTubeToBlogPipeline(PipelineOptions(generate_images=False))

        blog_data = {
            "title": "Test Title",
            "tags": ["tag1"],
            "blocks": [{"type": "paragraph", "text": "content"}],
        }
        with patch.object(
            pipeline,
            "convert_to_blog",
            new_callable=AsyncMock,
            return_value=blog_data,
        ):
            result = await pipeline.run("https://youtube.com/watch?v=test123")

        assert result.success is True
        assert result.title == "Test Title"
        assert "not published" in result.error

    @pytest.mark.asyncio
    @patch("app.services.youtube_to_blog.NaverBlogPlaywright")
    @patch("app.services.youtube_to_blog.fetch_transcript")
    @patch("app.services.youtube_to_blog.extract_video_id", return_value="test123")
    async def test_naver_publish_failure_returns_content(
        self, mock_vid, mock_fetch, mock_naver_cls,
    ):
        mock_fetch.return_value = [
            {"start": 0, "end": 5, "text": "hello"},
        ]

        mock_naver = MagicMock()
        mock_naver.has_session.return_value = True
        mock_naver.post = AsyncMock(return_value={"success": False, "error": "timeout"})
        mock_naver_cls.return_value = mock_naver

        pipeline = YouTubeToBlogPipeline(
            PipelineOptions(blog_id="testblog", generate_images=False),
        )

        blog_data = {
            "title": "Test Title",
            "tags": ["tag1"],
            "blocks": [{"type": "paragraph", "text": "content"}],
        }
        with patch.object(
            pipeline,
            "convert_to_blog",
            new_callable=AsyncMock,
            return_value=blog_data,
        ):
            result = await pipeline.run("https://youtube.com/watch?v=test123")

        assert result.success is True
        assert result.title == "Test Title"
        assert result.blocks == [{"type": "paragraph", "text": "content"}]
        assert "Naver publish error" in result.error

    @pytest.mark.asyncio
    async def test_dry_run_invalid_url(self):
        pipeline = YouTubeToBlogPipeline()
        result = await pipeline.run_dry("")
        assert result.success is False
        assert "Empty URL or ID" in result.error

    @pytest.mark.asyncio
    @patch("app.services.youtube_to_blog.fetch_transcript")
    @patch("app.services.youtube_to_blog.extract_video_id", return_value="dry123")
    async def test_dry_run_success(self, mock_vid, mock_fetch):
        mock_fetch.return_value = [
            {"start": 0, "end": 10, "text": "dry run text"},
        ]

        pipeline = YouTubeToBlogPipeline(PipelineOptions(generate_images=False))

        blog_data = {
            "title": "Dry Title",
            "tags": ["t1", "t2"],
            "blocks": [{"type": "heading2", "text": "Section"}],
        }
        with patch.object(
            pipeline,
            "convert_to_blog",
            new_callable=AsyncMock,
            return_value=blog_data,
        ):
            result = await pipeline.run_dry("https://youtube.com/watch?v=dry123")

        assert result.success is True
        assert result.title == "Dry Title"
        assert result.video_id == "dry123"
        assert result.blog_url == ""
