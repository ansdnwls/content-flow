"""Shared utilities for parsing Claude API responses."""
from __future__ import annotations

import json
from typing import Any


def strip_markdown_code_fence(text: str) -> str:
    """
    Remove markdown code fences from Claude responses.

    Handles:
    - ```json ... ```
    - ``` ... ```
    - Plain text (no fences)

    Args:
        text: Raw text from Claude response

    Returns:
        Text with code fences removed, stripped of whitespace
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.split("\n")
    if len(lines) < 2:
        return stripped

    # Remove first line (```json or ```)
    lines = lines[1:]
    # Remove last line if it's ```
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def parse_claude_json(text: str) -> Any:
    """
    Parse JSON from Claude response, handling markdown code fences.

    Args:
        text: Raw text from Claude response

    Returns:
        Parsed JSON (dict, list, or primitive)

    Raises:
        json.JSONDecodeError: If text is not valid JSON even after fence removal
    """
    cleaned = strip_markdown_code_fence(text)
    return json.loads(cleaned)


def extract_claude_text(payload: dict[str, Any]) -> str:
    """
    Extract all text content from Claude API response payload.

    Args:
        payload: Response dict from Anthropic messages API

    Returns:
        Concatenated text from all text-type content blocks
    """
    return "".join(
        part.get("text", "")
        for part in payload.get("content", [])
        if part.get("type") == "text"
    ).strip()
