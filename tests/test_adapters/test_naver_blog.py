"""Tests for Naver Blog adapter (Playwright-based)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.naver_blog import NaverBlogAdapter


CREDS: dict[str, str] = {"handle": "testblog"}


def adapter() -> NaverBlogAdapter:
    return NaverBlogAdapter()


class TestPublish:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True
        mock_pw.post = AsyncMock(return_value={
            "success": True,
            "url": "https://blog.naver.com/testblog/12345",
        })

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            result = await adapter().publish(
                "Hello Naver!", [], {"title": "Test Post"}, CREDS,
            )

        assert result.success
        assert "blog.naver.com" in result.url

    @pytest.mark.asyncio
    async def test_no_session(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = False

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            result = await adapter().publish("text", [], {}, CREDS)

        assert not result.success
        assert "session" in result.error.lower()

    @pytest.mark.asyncio
    async def test_playwright_error(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True
        mock_pw.post = AsyncMock(return_value={
            "success": False,
            "error": "Browser crash",
        })

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            result = await adapter().publish("text", [], {"title": "T"}, CREDS)

        assert not result.success
        assert "Browser crash" in result.error

    @pytest.mark.asyncio
    async def test_tags_from_string(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True
        mock_pw.post = AsyncMock(return_value={"success": True, "url": "https://blog.naver.com/x/1"})

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            await adapter().publish(
                "text", [], {"title": "T", "tags": "a, b, c"}, CREDS,
            )

        call_kwargs = mock_pw.post.call_args[1]
        assert call_kwargs["tags"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_tags_from_list(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True
        mock_pw.post = AsyncMock(return_value={"success": True, "url": "https://blog.naver.com/x/1"})

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            await adapter().publish(
                "text", [], {"title": "T", "tags": ["x", "y"]}, CREDS,
            )

        call_kwargs = mock_pw.post.call_args[1]
        assert call_kwargs["tags"] == ["x", "y"]

    @pytest.mark.asyncio
    async def test_blog_id_from_options(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True
        mock_pw.post = AsyncMock(return_value={"success": True, "url": "u"})

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ) as mock_cls:
            await adapter().publish(
                "text", [], {"title": "T", "blog_id": "myblog"}, {},
            )

        mock_cls.assert_called_once_with(blog_id="myblog")


class TestDelete:
    @pytest.mark.asyncio
    async def test_always_returns_false(self):
        assert await adapter().delete("12345", CREDS) is False


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_valid_session(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = True

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            assert await adapter().validate_credentials(CREDS) is True

    @pytest.mark.asyncio
    async def test_no_session(self):
        mock_pw = MagicMock()
        mock_pw.has_session.return_value = False

        with patch(
            "app.services.naver_blog_playwright.NaverBlogPlaywright",
            return_value=mock_pw,
        ):
            assert await adapter().validate_credentials(CREDS) is False
