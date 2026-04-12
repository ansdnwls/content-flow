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
