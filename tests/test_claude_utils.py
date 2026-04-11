"""Tests for Claude response parsing utilities."""
from __future__ import annotations

import json

import pytest

from app.core.claude_utils import (
    extract_claude_text,
    parse_claude_json,
    strip_markdown_code_fence,
)


class TestStripMarkdownCodeFence:
    """Test markdown code fence removal."""

    def test_no_fence(self):
        text = '{"key": "value"}'
        assert strip_markdown_code_fence(text) == '{"key": "value"}'

    def test_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_markdown_code_fence(text) == '{"key": "value"}'

    def test_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_markdown_code_fence(text) == '{"key": "value"}'

    def test_fence_with_whitespace(self):
        text = '  ```json\n{"key": "value"}\n```  '
        assert strip_markdown_code_fence(text) == '{"key": "value"}'

    def test_multiline_content(self):
        text = '```json\n{\n  "key": "value",\n  "num": 42\n}\n```'
        result = strip_markdown_code_fence(text)
        assert '"key"' in result
        assert '"num"' in result

    def test_empty_string(self):
        assert strip_markdown_code_fence("") == ""

    def test_only_fence(self):
        text = "```"
        result = strip_markdown_code_fence(text)
        assert isinstance(result, str)


class TestParseClaudeJson:
    """Test JSON parsing with fence handling."""

    def test_plain_json(self):
        result = parse_claude_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_claude_json(text)
        assert result == {"key": "value"}

    def test_json_array(self):
        text = '```json\n[1, 2, 3]\n```'
        result = parse_claude_json(text)
        assert result == [1, 2, 3]

    def test_nested_json(self):
        text = '```json\n{"items": [{"id": 1}, {"id": 2}]}\n```'
        result = parse_claude_json(text)
        assert result == {"items": [{"id": 1}, {"id": 2}]}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_claude_json("not json at all")


class TestExtractClaudeText:
    """Test text extraction from Claude API payload."""

    def test_single_text_block(self):
        payload = {
            "content": [
                {"type": "text", "text": "hello"}
            ]
        }
        assert extract_claude_text(payload) == "hello"

    def test_multiple_text_blocks(self):
        payload = {
            "content": [
                {"type": "text", "text": "hello "},
                {"type": "text", "text": "world"}
            ]
        }
        assert extract_claude_text(payload) == "hello world"

    def test_mixed_block_types(self):
        payload = {
            "content": [
                {"type": "text", "text": "before"},
                {"type": "tool_use", "name": "search"},
                {"type": "text", "text": "after"}
            ]
        }
        assert extract_claude_text(payload) == "beforeafter"

    def test_empty_content(self):
        assert extract_claude_text({"content": []}) == ""

    def test_missing_content(self):
        assert extract_claude_text({}) == ""
