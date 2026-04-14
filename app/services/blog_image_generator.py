"""Generate blog images via Vertex AI Imagen (primary) + pollinations.ai (fallback).

Flow:
1. Claude generates 2 English image prompts from blog title/content
2. Vertex AI Imagen 3.0 Fast renders each prompt (primary, uses GCP credits)
3. pollinations.ai as fallback if Vertex AI fails
4. Images are saved to a temp directory for upload
"""
from __future__ import annotations

import asyncio
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


# ---------------------------------------------------------------------------
# Vertex AI Imagen (primary — uses GCP credits via service account ADC)
# WARNING: GCP 콘솔에서 예산 알림 설정 필수 ($10/$50/$100 3단계 권장)
# https://console.cloud.google.com/billing/budgets?project=ytfactory-487714
# ---------------------------------------------------------------------------

_VERTEX_MODEL = "imagen-3.0-fast-generate-001"
_VERTEX_LOCATION = "us-central1"


async def generate_vertex_image(
    prompt: str,
    dest: Path,
    *,
    aspect_ratio: str = "4:5",
) -> Path | None:
    """Generate an image using Vertex AI Imagen 3.0 Fast via google-genai.

    Requires:
    - GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON
    - GOOGLE_CLOUD_PROJECT env var (or google_cloud_project in settings)
    - roles/aiplatform.user on the service account

    Args:
        prompt: English image prompt.
        dest: Destination file path for the generated image.
        aspect_ratio: Image aspect ratio (default "4:5" for 1080x1350 cards).
    """
    import os

    settings = get_settings()
    project = settings.google_cloud_project
    sa_path = settings.google_service_account_json_path

    if not project:
        logger.debug("vertex_image_skip_no_project")
        return None
    if not sa_path or not Path(sa_path).exists():
        logger.debug("vertex_image_skip_no_sa", path=sa_path)
        return None

    # Ensure ADC env var is set for google-genai
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", sa_path)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=project,
            location=_VERTEX_LOCATION,
        )

        response = await asyncio.to_thread(
            client.models.generate_images,
            model=_VERTEX_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
            ),
        )

        if response.generated_images:
            img_bytes = response.generated_images[0].image.image_bytes
            dest.write_bytes(img_bytes)
            logger.info(
                "vertex_image_generated",
                path=str(dest),
                size=len(img_bytes),
                model=_VERTEX_MODEL,
            )
            return dest

        logger.warning("vertex_image_no_result")
    except Exception as exc:
        logger.warning("vertex_image_failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# Google AI Studio fallback (uses GOOGLE_AI_API_KEY, no GCP credits)
# ---------------------------------------------------------------------------


async def generate_gemini_image(
    prompt: str,
    dest: Path,
) -> Path | None:
    """Generate an image using Google AI Studio (Gemini).

    Fallback when Vertex AI is unavailable. Uses GOOGLE_AI_API_KEY.
    """
    settings = get_settings()
    if not settings.google_ai_api_key:
        logger.debug("gemini_image_skip_no_api_key")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.google_ai_api_key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.1-flash-image-preview",
            contents=f"Generate an image: {prompt}",
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    dest.write_bytes(part.inline_data.data)
                    logger.info(
                        "gemini_image_generated",
                        path=str(dest),
                        size=len(part.inline_data.data),
                    )
                    return dest

        logger.warning("gemini_image_no_result")
    except Exception as exc:
        logger.warning("gemini_image_failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# Unified fallback chain: Vertex AI → Google AI Studio → pollinations.ai
# ---------------------------------------------------------------------------


async def generate_image(
    prompt: str,
    dest: Path,
    *,
    aspect_ratio: str = "4:5",
) -> Path | None:
    """Generate an image with 3-tier fallback.

    1. Vertex AI Imagen 3.0 (GCP credits, service account)
    2. Google AI Studio / Gemini (API key, no GCP credits)
    3. pollinations.ai (free, lower quality)
    """
    # Tier 1: Vertex AI
    result = await generate_vertex_image(prompt, dest, aspect_ratio=aspect_ratio)
    if result:
        return result

    # Tier 2: Google AI Studio
    result = await generate_gemini_image(prompt, dest)
    if result:
        return result

    # Tier 3: pollinations.ai
    logger.info("fallback_to_pollinations", prompt=prompt[:50])
    return await download_pollinations_image(prompt, dest)


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
        result = await generate_image(prompt, dest)
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
            result = await generate_image(block["prompt"], dest)
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
