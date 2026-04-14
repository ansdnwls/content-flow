"""Card news generator: YouTube transcript -> 10 PNG cards (1080x1350).

Pipeline:
1. Extract transcript via youtube_transcript.py
2. Claude plans 10 cards (JSON)
3. Gemini generates background images (parallel batches)
4. HTML cards rendered per card-news-guide.md design rules
5. Playwright captures each card as 1080x1350 PNG
"""
from __future__ import annotations

import asyncio
import base64
import html as html_mod
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.core.claude_utils import extract_claude_text, parse_claude_json
from app.core.logging_config import get_logger
from app.services.blog_image_generator import generate_gemini_image
from app.services.youtube_transcript import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CARD_WIDTH = 1080
CARD_HEIGHT = 1350
CARD_COUNT = 10


@dataclass
class CardSpec:
    """Single card specification from Claude planning."""

    index: int
    title: str
    body: str
    layout: str  # fullbleed | split | textonly
    image_prompt: str
    card_type: str  # cover | content | cta


@dataclass
class CardNewsResult:
    """Result of the card news generation pipeline."""

    success: bool
    video_id: str = ""
    card_count: int = 0
    output_dir: str = ""
    cards: list[CardSpec] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Claude prompt
# ---------------------------------------------------------------------------

_CARD_PLANNING_SYSTEM = (
    "You are a Korean card news content planner for Instagram.\n"
    "Given a YouTube transcript, plan exactly 10 cards for a card news post.\n"
    "\n"
    "Design rules:\n"
    "- Card 1: Cover card (title card with hook)\n"
    "- Cards 2-9: Content cards (one key message per card)\n"
    "- Card 10: CTA card (call-to-action: invite to watch the full YouTube video)\n"
    "- Body text: MAX 2-3 lines per card (mobile readability)\n"
    "- Title: short, impactful (under 20 chars)\n"
    "- All text in Korean, friendly tone\n"
    "\n"
    "Layout types (assign one per card):\n"
    "- fullbleed: Full background image + text overlay (best for visual impact)\n"
    "- split: Left 48% text / Right 52% image (best for info-heavy cards)\n"
    "- textonly: Gradient background + text only (for quotes, emphasis)\n"
    "\n"
    "Return a JSON array of 10 objects (no markdown fences):\n"
    "[\n"
    '  {"index": 1, "title": "cover title", "body": "subtitle or hook",\n'
    '   "layout": "fullbleed", "image_prompt": "English prompt for AI image, NO text in image",\n'
    '   "card_type": "cover"},\n'
    '  {"index": 2, "title": "section title", "body": "2-3 lines of content",\n'
    '   "layout": "split", "image_prompt": "English prompt...",\n'
    '   "card_type": "content"},\n'
    "  ...\n"
    '  {"index": 10, "title": "CTA title", "body": "full video link invitation",\n'
    '   "layout": "textonly", "image_prompt": "",\n'
    '   "card_type": "cta"}\n'
    "]\n"
    "\n"
    "Image prompt rules:\n"
    "- MUST start with: DO NOT include any text, letters, words, numbers, watermarks, logos.\n"
    "- Write in English, 50-100 words\n"
    "- Describe lighting, composition, colors, mood\n"
    "- Style: editorial magazine photography\n"
    "- textonly cards: leave image_prompt as empty string\n"
)


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape text and convert newlines to <br>."""
    return html_mod.escape(text).replace("\n", "<br>")


def _image_to_data_uri(file_path: str) -> str:
    """Convert an image file to a base64 data URI."""
    path = Path(file_path)
    if not path.exists():
        return ""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_card_html(
    card: CardSpec,
    image_path: str | None,
    total: int,
) -> str:
    """Build a complete single-card HTML page with all styles inlined."""
    w = CARD_WIDTH
    h = CARD_HEIGHT

    # Convert image to base64 data URI (no file:// paths)
    img_data_uri = ""
    if image_path:
        img_data_uri = _image_to_data_uri(image_path)

    # Build card body based on layout
    if card.layout == "fullbleed":
        bg_style = f"background-image:url('{img_data_uri}');" if img_data_uri else "background:#0A0A0A;"
        card_body = (
            f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;'
            f'background-size:cover;background-position:center;{bg_style}">\n'
            f'  <div style="position:absolute;bottom:0;left:0;right:0;'
            f'padding:60px 64px 80px;'
            f'background:linear-gradient(transparent 0%,rgba(10,10,10,0.85) 40%,rgba(10,10,10,0.95) 100%);">\n'
            f'    <div style="font-family:\'Noto Serif KR\',serif;font-size:48px;font-weight:900;'
            f'color:#FAFAFA;line-height:1.25;margin-bottom:20px;">{_esc(card.title)}</div>\n'
            f'    <div style="font-size:36px;font-weight:300;color:rgba(250,250,250,0.85);'
            f'line-height:1.55;">{_esc(card.body)}</div>\n'
            f'  </div>\n'
            f'  <div style="position:absolute;bottom:32px;left:50%;transform:translateX(-50%);'
            f'font-size:28px;font-weight:300;letter-spacing:3px;'
            f'color:rgba(250,250,250,0.5);">{card.index}/{total}</div>\n'
            f'</div>\n'
        )
    elif card.layout == "split":
        bg_style = f"background-image:url('{img_data_uri}');" if img_data_uri else "background:#CCCCCC;"
        card_body = (
            f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;display:flex;">\n'
            f'  <div style="width:48%;background:#FAFAFA;padding:80px 48px 80px 56px;'
            f'display:flex;flex-direction:column;justify-content:center;position:relative;">\n'
            f'    <div style="font-family:\'Noto Serif KR\',serif;font-size:48px;font-weight:900;'
            f'color:#0A0A0A;line-height:1.25;margin-bottom:20px;">{_esc(card.title)}</div>\n'
            f'    <div style="font-size:36px;font-weight:300;color:#555;'
            f'line-height:1.55;">{_esc(card.body)}</div>\n'
            f'    <div style="position:absolute;bottom:32px;left:50%;transform:translateX(-50%);'
            f'font-size:28px;font-weight:300;letter-spacing:3px;color:#999;">{card.index}/{total}</div>\n'
            f'  </div>\n'
            f'  <div style="width:52%;background-size:cover;background-position:center;'
            f'{bg_style}"></div>\n'
            f'</div>\n'
        )
    else:
        # textonly
        is_dark = card.index % 2 != 0
        bg_color = "#0A0A0A" if is_dark else "#FAFAFA"
        title_color = "#FAFAFA" if is_dark else "#0A0A0A"
        body_color = "rgba(250,250,250,0.85)" if is_dark else "#555"
        page_color = "rgba(250,250,250,0.5)" if is_dark else "#999"
        card_body = (
            f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;'
            f'display:flex;flex-direction:column;justify-content:center;align-items:center;'
            f'text-align:center;padding:80px 72px;background:{bg_color};">\n'
            f'  <div style="font-family:\'Noto Serif KR\',serif;font-size:56px;font-weight:900;'
            f'color:{title_color};line-height:1.25;margin-bottom:32px;">{_esc(card.title)}</div>\n'
            f'  <div style="font-size:36px;font-weight:300;color:{body_color};'
            f'line-height:1.55;">{_esc(card.body)}</div>\n'
            f'  <div style="position:absolute;bottom:32px;left:50%;transform:translateX(-50%);'
            f'font-size:28px;font-weight:300;letter-spacing:3px;color:{page_color};">{card.index}/{total}</div>\n'
            f'</div>\n'
        )

    return (
        '<!DOCTYPE html>\n'
        '<html lang="ko">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900'
        '&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">\n'
        '<style>\n'
        f'* {{ margin:0; padding:0; box-sizing:border-box; }}\n'
        f'body {{ width:{w}px; height:{h}px; overflow:hidden; '
        f"font-family:'Noto Sans KR',sans-serif; }}\n"
        '</style>\n'
        '</head>\n'
        '<body>\n'
        + card_body +
        '</body>\n'
        '</html>'
    )


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class CardNewsGenerator:
    """Generate Instagram card news PNGs from a YouTube video."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def generate(self, youtube_url: str) -> CardNewsResult:
        """Full pipeline: transcript -> cards -> images -> PNGs."""
        # 1. Extract transcript
        try:
            video_id = extract_video_id(youtube_url)
        except TranscriptError as exc:
            return CardNewsResult(success=False, error=str(exc))

        logger.info("card_news_start", video_id=video_id)

        try:
            segments = fetch_transcript(video_id)
        except TranscriptError as exc:
            return CardNewsResult(success=False, video_id=video_id, error=str(exc))

        raw_text = " ".join(seg["text"] for seg in segments)
        truncated = raw_text[:3000]
        if len(raw_text) > 3000:
            truncated += "...(이하 생략)"

        # 2. Claude card planning
        try:
            cards = await self._plan_cards(truncated, video_id)
        except Exception as exc:
            err_detail = str(exc) or repr(exc)
            logger.error("card_news_plan_failed", video_id=video_id, error=err_detail)
            return CardNewsResult(
                success=False,
                video_id=video_id,
                error=f"Card planning failed ({type(exc).__name__}): {err_detail}",
            )

        logger.info("card_news_planned", video_id=video_id, card_count=len(cards))

        # 3. Generate background images (parallel batches of 3)
        image_map = await self._generate_images(cards)
        logger.info("card_news_images_done", video_id=video_id, count=len(image_map))

        # 4-5. HTML -> Playwright PNG capture
        output_dir = Path(f"output/card_news/{video_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        png_paths = await self._render_pngs(cards, image_map, output_dir)
        logger.info("card_news_complete", video_id=video_id, pngs=len(png_paths))

        return CardNewsResult(
            success=True,
            video_id=video_id,
            card_count=len(cards),
            output_dir=str(output_dir),
            cards=cards,
            image_paths=png_paths,
        )

    # ------------------------------------------------------------------
    # Stage 2: Claude card planning
    # ------------------------------------------------------------------

    async def _plan_cards(
        self, transcript_text: str, video_id: str,
    ) -> list[CardSpec]:
        if not self._settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        user_msg = (
            f"YouTube Video ID: {video_id}\n"
            f"YouTube URL: https://www.youtube.com/watch?v={video_id}\n\n"
            f"Transcript:\n{transcript_text}"
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
                    "system": _CARD_PLANNING_SYSTEM,
                    "messages": [{"role": "user", "content": user_msg}],
                },
            )
            resp.raise_for_status()
            payload = resp.json()

        raw_text = extract_claude_text(payload)
        card_list: list[dict[str, Any]] = parse_claude_json(raw_text)

        if not isinstance(card_list, list) or len(card_list) == 0:
            raise ValueError(f"Expected non-empty list from Claude, got {type(card_list).__name__}")

        cards: list[CardSpec] = []
        for item in card_list[:CARD_COUNT]:
            layout = item.get("layout", "textonly")
            if layout not in ("fullbleed", "split", "textonly"):
                layout = "textonly"
            cards.append(CardSpec(
                index=item.get("index", len(cards) + 1),
                title=item.get("title", ""),
                body=item.get("body", ""),
                layout=layout,
                image_prompt=item.get("image_prompt", ""),
                card_type=item.get("card_type", "content"),
            ))

        return cards

    # ------------------------------------------------------------------
    # Stage 3: Gemini image generation (parallel batches)
    # ------------------------------------------------------------------

    async def _generate_images(
        self, cards: list[CardSpec],
    ) -> dict[int, str]:
        """Generate images for cards that need them. Returns {card_index: file_path}."""
        needs_image = [
            c for c in cards
            if c.layout in ("fullbleed", "split") and c.image_prompt
        ]

        if not needs_image:
            return {}

        temp_dir = Path(tempfile.mkdtemp(prefix="card_img_"))
        image_map: dict[int, str] = {}

        # Process in batches of 3 to avoid rate limits
        batch_size = 3
        for i in range(0, len(needs_image), batch_size):
            batch = needs_image[i : i + batch_size]
            tasks = []
            for card in batch:
                dest = temp_dir / f"card_{card.index:02d}.png"
                tasks.append(self._gen_single_image(card.image_prompt, dest, card.index))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for card, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning(
                        "card_image_failed",
                        index=card.index,
                        error=str(result),
                    )
                elif result:
                    image_map[card.index] = result

        return image_map

    async def _gen_single_image(
        self, prompt: str, dest: Path, index: int,
    ) -> str | None:
        """Generate a single image, return file path or None."""
        result = await generate_gemini_image(prompt, dest)
        if result:
            return str(result)
        logger.warning("card_image_skip", index=index)
        return None

    # ------------------------------------------------------------------
    # Stage 4-5: HTML render + Playwright PNG capture
    # ------------------------------------------------------------------

    async def _render_pngs(
        self,
        cards: list[CardSpec],
        image_map: dict[int, str],
        output_dir: Path,
    ) -> list[str]:
        """Render each card as HTML, capture with Playwright as PNG."""
        from playwright.async_api import async_playwright

        png_paths: list[str] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
            )

            for card in cards:
                img_path = image_map.get(card.index)
                card_html = build_card_html(card, img_path, len(cards))

                # Write temp HTML and load via file:// protocol
                tmp_html = output_dir / f"_card_{card.index:02d}.html"
                tmp_html.write_text(card_html, encoding="utf-8")

                await page.goto(f"file:///{tmp_html.resolve().as_posix()}")
                # Wait for Google Fonts to load
                await page.wait_for_load_state("networkidle")
                # Extra wait for font rendering to complete
                await page.wait_for_timeout(1000)

                png_path = output_dir / f"card_{card.index:02d}.png"
                await page.screenshot(path=str(png_path), type="png")
                png_paths.append(str(png_path))

                # Clean up temp HTML
                tmp_html.unlink(missing_ok=True)

                logger.info(
                    "card_png_captured",
                    index=card.index,
                    layout=card.layout,
                    path=str(png_path),
                )

            await browser.close()

        return png_paths
