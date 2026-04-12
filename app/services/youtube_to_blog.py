"""YouTube -> Naver Blog auto-publishing pipeline.

Orchestrates: transcript extraction -> Claude blog conversion ->
AI image generation -> Naver Blog publishing.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.core.claude_utils import extract_claude_text, parse_claude_json
from app.core.logging_config import get_logger
from app.services.blog_image_generator import download_pollinations_image
from app.services.naver_blog_playwright import NaverBlogPlaywright
from app.services.youtube_transcript import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineOptions:
    """Configuration for a single pipeline run."""

    blog_id: str | None = None
    extra_tags: list[str] = field(default_factory=list)
    generate_images: bool = True
    max_transcript_chars: int = 4000


@dataclass
class PipelineResult:
    """Outcome of a pipeline run."""

    success: bool
    video_id: str = ""
    title: str = ""
    tags: list[str] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    blog_url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Claude prompt
# ---------------------------------------------------------------------------

_TRANSCRIPT_TO_BLOG_SYSTEM = (
    "You are a Korean blog content writer for YouTube creators.\n"
    "Given a YouTube video transcript, transform it into an engaging blog post.\n"
    "\n"
    "IMPORTANT RULES:\n"
    "- Do NOT copy the transcript verbatim. Rewrite it as a proper blog article.\n"
    "- Write in Korean with a friendly, conversational tone.\n"
    "- Target length: 1500-2500 characters (Korean).\n"
    "- Structure the post with clear sections.\n"
    "\n"
    "Return a single JSON object (no markdown fences):\n"
    "{\n"
    '  "title": "SEO-friendly blog title, under 30 chars, in Korean",\n'
    '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],\n'
    '  "blocks": [\n'
    '    {"type": "heading2", "text": "section title"},\n'
    '    {"type": "paragraph", "text": "body text..."},\n'
    '    {"type": "quote", "text": "quote text", "style": "vertical"},\n'
    '    {"type": "image", "prompt": "English image prompt for AI generation"},\n'
    '    {"type": "highlight", "text": "key point", "color": "blue"},\n'
    '    {"type": "divider"},\n'
    '    {"type": "paragraph", "text": "closing text..."}\n'
    "  ]\n"
    "}\n"
    "\n"
    "Block types available:\n"
    "- heading2: Section title (use 2-3 per post)\n"
    "- paragraph: Body text (2-4 sentences each)\n"
    "- quote: Memorable quote (style: vertical|bubble|sticker, vary styles)\n"
    "- image: AI illustration (prompt in English, 2-3 per post)\n"
    "- highlight: Key takeaway (color: red|blue|green|orange, 1-2 per post)\n"
    "- divider: Section separator\n"
    "\n"
    "MUST include at the end:\n"
    "- A paragraph with a call-to-action directing readers to the YouTube video.\n"
    "- Provide 5-10 Korean hashtags in the tags array.\n"
)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class YouTubeToBlogPipeline:
    """Orchestrate the full YouTube-to-blog conversion."""

    def __init__(self, options: PipelineOptions | None = None) -> None:
        self.options = options or PipelineOptions()
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def run(
        self,
        youtube_url: str,
        naver_account_id: str | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline: transcript -> blog -> images -> publish."""
        # 1. Extract transcript
        try:
            video_id, segments = self.extract_transcript(youtube_url)
        except TranscriptError as exc:
            return PipelineResult(success=False, error=str(exc))

        # 2. Convert to blog via Claude (hard error)
        raw_text = " ".join(seg["text"] for seg in segments)
        truncated = raw_text[: self.options.max_transcript_chars]

        try:
            blog_data = await self.convert_to_blog(truncated, video_id)
        except Exception as exc:
            err_detail = str(exc) or repr(exc)
            logger.error(
                "pipeline_claude_failed",
                video_id=video_id,
                error=err_detail,
                error_type=type(exc).__name__,
            )
            return PipelineResult(
                success=False,
                video_id=video_id,
                error=f"Claude conversion failed ({type(exc).__name__}): {err_detail}",
            )

        title: str = blog_data.get("title", "")
        tags: list[str] = blog_data.get("tags", [])
        blocks: list[dict[str, Any]] = blog_data.get("blocks", [])

        if self.options.extra_tags:
            tags = list(dict.fromkeys(tags + self.options.extra_tags))

        logger.info(
            "pipeline_blog_generated",
            video_id=video_id,
            title=title[:50],
            block_count=len(blocks),
            tag_count=len(tags),
        )

        # 3. Render images (non-fatal)
        if self.options.generate_images:
            blocks = await self._render_images(blocks)

        result = PipelineResult(
            success=True,
            video_id=video_id,
            title=title,
            tags=tags,
            blocks=blocks,
        )

        # 4. Publish to Naver Blog
        try:
            result = await self.publish(
                structured_content=blocks,
                title=title,
                tags=tags,
                naver_account_id=naver_account_id,
                result=result,
            )
        except Exception as exc:
            result.error = f"Naver publish failed: {exc}"
            logger.error("pipeline_naver_failed", video_id=video_id, error=str(exc))

        return result

    async def run_dry(self, youtube_url: str) -> PipelineResult:
        """Run transcript + Claude conversion only (skip Naver publish)."""
        try:
            video_id, segments = self.extract_transcript(youtube_url)
        except TranscriptError as exc:
            return PipelineResult(success=False, error=str(exc))

        raw_text = " ".join(seg["text"] for seg in segments)
        truncated = raw_text[: self.options.max_transcript_chars]

        try:
            blog_data = await self.convert_to_blog(truncated, video_id)
        except Exception as exc:
            err_detail = str(exc) or repr(exc)
            return PipelineResult(
                success=False,
                video_id=video_id,
                error=f"Claude conversion failed ({type(exc).__name__}): {err_detail}",
            )

        title = blog_data.get("title", "")
        tags = blog_data.get("tags", [])
        blocks = blog_data.get("blocks", [])

        if self.options.extra_tags:
            tags = list(dict.fromkeys(tags + self.options.extra_tags))

        if self.options.generate_images:
            blocks = await self._render_images(blocks)

        return PipelineResult(
            success=True,
            video_id=video_id,
            title=title,
            tags=tags,
            blocks=blocks,
        )

    # ------------------------------------------------------------------
    # Pipeline stages (public for testability)
    # ------------------------------------------------------------------

    def extract_transcript(
        self, youtube_url: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Extract video ID and transcript segments from a YouTube URL.

        Returns:
            (video_id, segments) tuple.

        Raises:
            TranscriptError: On invalid URL or transcript fetch failure.
        """
        video_id = extract_video_id(youtube_url)
        logger.info("pipeline_start", video_id=video_id)

        segments = fetch_transcript(video_id)
        logger.info(
            "pipeline_transcript_ok",
            video_id=video_id,
            segment_count=len(segments),
        )
        return video_id, segments

    async def convert_to_blog(
        self,
        transcript_text: str,
        video_id: str,
    ) -> dict[str, Any]:
        """Call Claude API to convert transcript into structured blog content.

        Returns:
            Dict with keys: title, tags, blocks.

        Raises:
            RuntimeError: If API key is missing.
            ValueError: If Claude response is malformed.
        """
        if not self._settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        _MAX_TRANSCRIPT_CHARS = 3000
        if len(transcript_text) > _MAX_TRANSCRIPT_CHARS:
            truncated = transcript_text[:_MAX_TRANSCRIPT_CHARS] + "...(이하 생략)"
        else:
            truncated = transcript_text

        user_msg = (
            f"YouTube Video ID: {video_id}\n"
            f"YouTube URL: https://www.youtube.com/watch?v={video_id}\n\n"
            f"Transcript:\n{truncated}"
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._settings.anthropic_api_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": self._settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._settings.anthropic_model,
                    "max_tokens": 4000,
                    "system": _TRANSCRIPT_TO_BLOG_SYSTEM,
                    "messages": [{"role": "user", "content": user_msg}],
                },
            )
            resp.raise_for_status()
            payload = resp.json()

        raw_text = extract_claude_text(payload)
        blog_data: dict[str, Any] = parse_claude_json(raw_text)

        if not isinstance(blog_data, dict):
            raise ValueError(f"Expected dict from Claude, got {type(blog_data).__name__}")
        if "blocks" not in blog_data:
            raise ValueError("Claude response missing 'blocks' key")

        return blog_data

    async def publish(
        self,
        structured_content: list[dict[str, Any]],
        title: str,
        tags: list[str],
        naver_account_id: str | None = None,
        result: PipelineResult | None = None,
    ) -> PipelineResult:
        """Publish structured content to Naver Blog.

        If *result* is provided it is updated in-place and returned;
        otherwise a new PipelineResult is created.
        """
        if result is None:
            result = PipelineResult(
                success=True,
                title=title,
                tags=tags,
                blocks=structured_content,
            )

        blog_id = naver_account_id or self.options.blog_id or self._settings.naver_blog_id
        if not blog_id:
            result.error = "NAVER_BLOG_ID not configured; content generated but not published."
            logger.warning("pipeline_no_blog_id")
            return result

        naver = NaverBlogPlaywright(blog_id=blog_id)
        if not naver.has_session():
            result.error = "No Naver session file; content generated but not published."
            logger.warning("pipeline_no_session")
            return result

        pub_result = await naver.post(
            title=title,
            content=structured_content,
            tags=tags,
        )

        if pub_result.get("success"):
            result.blog_url = pub_result.get("url", "")
            logger.info(
                "pipeline_complete",
                video_id=result.video_id,
                blog_url=result.blog_url,
            )
        else:
            result.error = f"Naver publish error: {pub_result.get('error', 'unknown')}"
            logger.error("pipeline_naver_error", error=result.error)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _render_images(
        self, blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Download AI images for image blocks. Non-fatal on failure."""
        temp_dir = Path(tempfile.mkdtemp(prefix="pipeline_img_"))
        img_idx = 0
        rendered: list[dict[str, Any]] = []

        for block in blocks:
            if block.get("type") == "image" and block.get("prompt"):
                dest = temp_dir / f"pipe_img_{img_idx}.jpg"
                try:
                    path = await download_pollinations_image(block["prompt"], dest)
                    if path:
                        rendered.append({
                            "type": "image",
                            "url": str(path),
                            "caption": block.get("caption", ""),
                        })
                        img_idx += 1
                        continue
                except Exception as exc:
                    logger.warning(
                        "pipeline_image_failed",
                        prompt=block["prompt"][:50],
                        error=str(exc),
                    )
                # Skip failed image blocks
            else:
                rendered.append(block)

        logger.info("pipeline_images_rendered", total=img_idx)
        return rendered
