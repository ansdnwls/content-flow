"""Tests for NaverBlogPlaywright service."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.naver_blog_playwright import NaverBlogPlaywright, _random_delay


# ---------------------------------------------------------------------------
# _random_delay
# ---------------------------------------------------------------------------

class TestRandomDelay:
    def test_within_range(self):
        for _ in range(50):
            d = _random_delay(5, 20)
            assert 5 <= d <= 20

    def test_default_range(self):
        d = _random_delay()
        assert 3 <= d <= 30


# ---------------------------------------------------------------------------
# has_session
# ---------------------------------------------------------------------------

class TestHasSession:
    def test_returns_false_when_missing(self, tmp_path: Path):
        client = NaverBlogPlaywright(
            blog_id="test",
            session_path=str(tmp_path / "nonexistent.json"),
        )
        assert client.has_session() is False

    def test_returns_true_when_exists(self, tmp_path: Path):
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")
        client = NaverBlogPlaywright(
            blog_id="test",
            session_path=str(session_file),
        )
        assert client.has_session() is True


# ---------------------------------------------------------------------------
# post — error paths
# ---------------------------------------------------------------------------

class TestPostErrors:
    @pytest.mark.asyncio
    async def test_no_session_returns_error(self, tmp_path: Path):
        client = NaverBlogPlaywright(
            blog_id="test",
            session_path=str(tmp_path / "missing.json"),
        )
        result = await client.post(title="T", content="C")
        assert result["success"] is False
        assert "session" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_no_blog_id_returns_error(self, tmp_path: Path):
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")
        client = NaverBlogPlaywright(
            blog_id="",
            session_path=str(session_file),
        )
        result = await client.post(title="T", content="C")
        assert result["success"] is False
        assert "NAVER_BLOG_ID" in result["error"]


# ---------------------------------------------------------------------------
# _resolve_image
# ---------------------------------------------------------------------------

class TestResolveImage:
    @pytest.mark.asyncio
    async def test_local_file(self, tmp_path: Path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0")
        client = NaverBlogPlaywright(blog_id="t", session_path=str(tmp_path / "s.json"))
        result = await client._resolve_image(str(img), tmp_path, 0)
        assert result == img

    @pytest.mark.asyncio
    async def test_nonexistent_local_returns_none(self, tmp_path: Path):
        client = NaverBlogPlaywright(blog_id="t", session_path=str(tmp_path / "s.json"))
        result = await client._resolve_image("/no/such/file.jpg", tmp_path, 0)
        assert result is None

    @pytest.mark.asyncio
    async def test_http_url_downloads(self, tmp_path: Path):
        import httpx

        client = NaverBlogPlaywright(blog_id="t", session_path=str(tmp_path / "s.json"))

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"\xff\xd8fake_jpeg"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.naver_blog_playwright.httpx.AsyncClient", return_value=mock_client):
            result = await client._resolve_image("https://example.com/img.jpg", tmp_path, 0)

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"\xff\xd8fake_jpeg"


# ---------------------------------------------------------------------------
# _col_letter-style: test _type_section logic indirectly
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_defaults_from_settings(self):
        with patch("app.services.naver_blog_playwright.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                naver_blog_id="myblog",
                naver_session_path="/tmp/sess.json",
            )
            client = NaverBlogPlaywright()
            assert client.blog_id == "myblog"
            assert client.session_path == Path("/tmp/sess.json")

    def test_explicit_overrides(self):
        client = NaverBlogPlaywright(
            blog_id="override",
            session_path="/custom/path.json",
        )
        assert client.blog_id == "override"
        assert client.session_path == Path("/custom/path.json")
