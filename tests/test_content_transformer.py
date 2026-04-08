"""Tests for content_transformer — fallback and Claude integration."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from app.services.content_transformer import ContentTransformer

MODULE = "app.services.content_transformer"


@pytest.fixture()
def _patch_settings():
    with patch(f"{MODULE}.get_settings") as mock:
        s = mock.return_value
        s.anthropic_api_key = None
        s.anthropic_model = "claude-3-5-sonnet-latest"
        s.anthropic_api_base_url = "https://api.anthropic.com/v1"
        yield s


class TestFallbackTransform:
    @pytest.mark.usefixtures("_patch_settings")
    async def test_returns_all_platforms(self):
        result = await ContentTransformer().transform_topic("AI video editing")
        expected = {
            "youtube", "tiktok", "instagram", "x",
            "linkedin", "blog", "threads", "pinterest", "telegram",
        }
        assert set(result.keys()) == expected

    @pytest.mark.usefixtures("_patch_settings")
    async def test_each_platform_has_required_fields(self):
        result = await ContentTransformer().transform_topic("crypto regulation")
        for platform, content in result.items():
            assert "title" in content, f"{platform} missing title"
            assert "body" in content, f"{platform} missing body"
            assert "publish_status" in content, f"{platform} missing publish_status"
            assert content["publish_status"] == "draft"

    @pytest.mark.usefixtures("_patch_settings")
    async def test_youtube_body_mentions_topic(self):
        topic = "Korean cooking tips"
        result = await ContentTransformer().transform_topic(topic)
        assert topic in result["youtube"]["body"]

    @pytest.mark.usefixtures("_patch_settings")
    async def test_x_body_within_280_chars(self):
        result = await ContentTransformer().transform_topic(
            "A very long topic about many things in the world"
        )
        assert len(result["x"]["body"]) <= 280


class TestClaudeTransform:
    @respx.mock
    async def test_uses_claude_when_key_set(self, _patch_settings):
        _patch_settings.anthropic_api_key = "sk-test"

        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": '{"youtube": {"title": "test"}}'}],
            })
        )

        result = await ContentTransformer().transform_topic("test topic")
        assert result == {"youtube": {"title": "test"}}

    @respx.mock
    async def test_falls_back_on_claude_error(self, _patch_settings):
        _patch_settings.anthropic_api_key = "sk-test"

        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        result = await ContentTransformer().transform_topic("fallback topic")
        # Should get fallback result with all platforms
        assert "youtube" in result
        assert "tiktok" in result
