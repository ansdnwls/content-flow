"""Generate blog images via Claude prompt creation + pollinations.ai rendering.

Flow:
1. Claude generates 2 English image prompts from blog title/content
2. pollinations.ai renders each prompt into an image (free, no API key)
3. Images are saved to a temp directory for upload
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_PROMPT_SYSTEM = (
    "You are a blog illustration prompt generator. "
    "Given a blog title and summary, produce exactly 2 concise English image prompts "
    "suitable for a high-quality blog illustration. "
    "Return ONLY a JSON array of 2 strings, no markdown, no explanation. "
    'Example: ["prompt one", "prompt two"]'
)

_STRUCTURED_SYSTEM = (
    "You are a Korean blog content architect. Given a title and raw text, "
    "produce a structured blog post as a JSON array of content blocks.\n"
    "Available block types:\n"
    '  {"type":"heading2","text":"..."}\n'
    '  {"type":"heading3","text":"..."}\n'
    '  {"type":"paragraph","text":"..."}\n'
    '  {"type":"image","prompt":"English image prompt for AI generation"}\n'
    '  {"type":"quote","text":"...","style":"vertical|bubble|sticker"}\n'
    '  {"type":"highlight","text":"...","color":"red|blue|green|orange"}\n'
    '  {"type":"table","headers":["col1","col2"],"rows":[["val1","val2"]]}\n'
    '  {"type":"divider"}\n'
    "Rules:\n"
    "- Write all text content in Korean\n"
    "- Include 2-3 heading2 sections\n"
    "- Include 2-3 image blocks with English prompts\n"
    "- Include 2-3 quote blocks, each with a DIFFERENT style (vertical, bubble, sticker)\n"
    "- Include 1-2 highlight blocks for key takeaways\n"
    "- Include 0-2 table blocks when content has numbers, comparisons, or lists\n"
    "- Use dividers between major sections\n"
    "- Paragraphs should be 2-4 sentences each\n"
    "- Return ONLY the JSON array, no markdown fences"
)

_POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
_IMAGE_WIDTH = 800
_IMAGE_HEIGHT = 600


async def generate_image_prompts(
    title: str,
    content: str,
    *,
    max_content_chars: int = 500,
) -> list[str]:
    """Ask Claude to generate 2 image prompts for the blog post.

    Returns an empty list on any failure (non-fatal).
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("blog_image_skip_no_api_key")
        return []

    user_msg = (
        f"Blog title: {title}\n\n"
        f"Blog content summary:\n{content[:max_content_chars]}"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.anthropic_api_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 300,
                    "system": _PROMPT_SYSTEM,
                    "messages": [{"role": "user", "content": user_msg}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["content"][0]["text"].strip()
        prompts: list[str] = json.loads(text)
        if isinstance(prompts, list) and len(prompts) >= 1:
            logger.info("blog_image_prompts_generated", count=len(prompts))
            return prompts[:2]
    except Exception as exc:
        logger.warning("blog_image_prompt_failed", error=str(exc))

    return []


async def download_pollinations_image(
    prompt: str,
    dest: Path,
    *,
    width: int = _IMAGE_WIDTH,
    height: int = _IMAGE_HEIGHT,
) -> Path | None:
    """Download a generated image from pollinations.ai.

    Returns the saved file path, or None on failure.
    """
    encoded = quote(prompt, safe="")
    url = f"{_POLLINATIONS_BASE}/{encoded}?width={width}&height={height}&nologo=true"

    try:
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest.write_bytes(resp.content)
                logger.info(
                    "blog_image_downloaded",
                    path=str(dest),
                    size=len(resp.content),
                )
                return dest
            logger.warning(
                "blog_image_download_bad_response",
                status=resp.status_code,
                size=len(resp.content),
            )
    except Exception as exc:
        logger.warning("blog_image_download_failed", error=str(exc))

    return None


async def generate_blog_images(
    title: str,
    content: str,
) -> list[Path]:
    """End-to-end: generate prompts via Claude, render via pollinations.ai.

    Returns list of local image file paths (0-2 items). Non-fatal on
    any failure — returns whatever images were successfully generated.
    """
    prompts = await generate_image_prompts(title, content)
    if not prompts:
        return []

    temp_dir = Path(tempfile.mkdtemp(prefix="blog_img_"))
    images: list[Path] = []

    for i, prompt in enumerate(prompts):
        dest = temp_dir / f"blog_image_{i}.jpg"
        result = await download_pollinations_image(prompt, dest)
        if result:
            images.append(result)

    logger.info("blog_images_ready", count=len(images), total_prompts=len(prompts))
    return images


# ---------------------------------------------------------------------------
# Structured content generation
# ---------------------------------------------------------------------------


async def generate_structured_content(
    title: str,
    text: str,
    *,
    max_text_chars: int = 1500,
) -> list[dict[str, Any]]:
    """Use Claude to generate structured blog content blocks.

    Returns a list of content block dicts.  Image blocks contain a
    ``prompt`` key whose value is rendered via pollinations.ai and
    replaced with a ``url`` key pointing to the downloaded file.

    Returns an empty list on failure (non-fatal).
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("structured_content_skip_no_api_key")
        return []

    user_msg = (
        f"Blog title: {title}\n\n"
        f"Raw content:\n{text[:max_text_chars]}"
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.anthropic_api_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 2000,
                    "system": _STRUCTURED_SYSTEM,
                    "messages": [{"role": "user", "content": user_msg}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw = data["content"][0]["text"].strip()
        # Strip markdown fences if Claude adds them anyway
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        blocks: list[dict[str, Any]] = json.loads(raw.strip())
        if not isinstance(blocks, list):
            return []

        logger.info("structured_content_generated", block_count=len(blocks))
    except Exception as exc:
        logger.warning("structured_content_failed", error=str(exc))
        return []

    # Render image prompts via pollinations.ai
    temp_dir = Path(tempfile.mkdtemp(prefix="struct_img_"))
    img_idx = 0
    rendered_blocks: list[dict[str, Any]] = []

    for block in blocks:
        if block.get("type") == "image" and block.get("prompt"):
            dest = temp_dir / f"struct_img_{img_idx}.jpg"
            result = await download_pollinations_image(block["prompt"], dest)
            if result:
                rendered_blocks.append({
                    "type": "image",
                    "url": str(result),
                    "caption": block.get("caption", ""),
                })
                img_idx += 1
            else:
                logger.warning("structured_image_render_failed", prompt=block["prompt"][:50])
                # Skip failed images
        else:
            rendered_blocks.append(block)

    logger.info(
        "structured_content_ready",
        total_blocks=len(rendered_blocks),
        images=img_idx,
    )
    return rendered_blocks
