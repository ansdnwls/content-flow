"""Card news generator: YouTube transcript -> 10 PNG cards (1080x1350).

Pipeline:
1. Extract transcript via youtube_transcript.py
2. Claude plans 10 cards with card_type (cover/content/tip/closing/cta)
3. Gemini generates images: cover=2K cinematic, content=1K (max 4)
4. HTML cards rendered per card type design rules
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

_VALID_CARD_TYPES = {"cover", "content", "tip", "closing", "cta"}


@dataclass
class CardSpec:
    """Single card specification from Claude planning."""

    index: int
    title: str
    body: str
    layout: str  # fullbleed | split | textonly
    image_prompt: str
    card_type: str  # cover | content | tip | closing | cta


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
    "Card types (assign one per card):\n"
    "- cover: Card 1 only. Eye-catching title card with a hook.\n"
    "- content: Cards 2-7. One key message per card. Split layout (text left, image right).\n"
    "- tip: 1-2 cards among 2-9. Highlight a practical tip or key insight. Use a relevant emoji.\n"
    "- closing: Card 9. Emotional wrap-up, summary or takeaway.\n"
    "- cta: Card 10 only. Call-to-action inviting viewers to the full YouTube video.\n"
    "\n"
    "Rules:\n"
    "- Body text: MAX 2-3 lines per card (mobile readability)\n"
    "- Title: short, impactful (under 20 chars)\n"
    "- All text in Korean, friendly tone\n"
    "- tip cards: include a single relevant emoji in the title (e.g. '💡 핵심 포인트')\n"
    "- closing card: emotional, reflective tone\n"
    "- cta card: body should say '자세한 내용은 유튜브에서 확인하세요'\n"
    "\n"
    "Return a JSON array of 10 objects (no markdown fences):\n"
    "[\n"
    '  {"index": 1, "title": "cover title", "body": "subtitle or hook",\n'
    '   "layout": "fullbleed", "image_prompt": "English prompt for 2K cinematic AI image, NO text in image",\n'
    '   "card_type": "cover"},\n'
    '  {"index": 2, "title": "section title", "body": "2-3 lines of content",\n'
    '   "layout": "split", "image_prompt": "English prompt for 1K image...",\n'
    '   "card_type": "content"},\n'
    "  ...\n"
    '  {"index": 8, "title": "💡 tip title", "body": "practical tip text",\n'
    '   "layout": "textonly", "image_prompt": "",\n'
    '   "card_type": "tip"},\n'
    '  {"index": 9, "title": "closing title", "body": "emotional wrap-up",\n'
    '   "layout": "textonly", "image_prompt": "",\n'
    '   "card_type": "closing"},\n'
    '  {"index": 10, "title": "CTA title", "body": "full video link invitation",\n'
    '   "layout": "textonly", "image_prompt": "",\n'
    '   "card_type": "cta"}\n'
    "]\n"
    "\n"
    "Image prompt rules:\n"
    "- cover: MUST start with 'DO NOT include any text, letters, words, numbers, watermarks, logos.'\n"
    "  Write in English, 80-120 words, cinematic quality, dramatic lighting, 2K resolution feel\n"
    "- content: MUST start with same prefix. English, 50-80 words, editorial style\n"
    "- tip/closing/cta: leave image_prompt as empty string (no image needed)\n"
)


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

_ACCENT_BLUE = "#1a6cf5"
_ACCENT_GOLD = "#f7971e"
_PAD_LR = 80


# ---------------------------------------------------------------------------
# HTML helpers
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


def _page_num_html(index: int, total: int, color: str) -> str:
    """Bottom-right page number."""
    return (
        f'<div style="position:absolute;bottom:28px;right:32px;'
        f'font-size:24px;font-weight:300;letter-spacing:2px;'
        f'color:{color};">{index}/{total}</div>'
    )


def _accent_line(color: str = _ACCENT_BLUE, centered: bool = False) -> str:
    """Accent line under title."""
    margin = "16px auto 20px" if centered else "16px 0 20px"
    return (
        f'<div style="width:40px;height:2px;background:{color};'
        f'margin:{margin};"></div>'
    )


def _wrap_html(card_body: str) -> str:
    """Wrap card body in full HTML page with fonts."""
    w, h = CARD_WIDTH, CARD_HEIGHT
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
# Card type builders
# ---------------------------------------------------------------------------

def _build_cover(card: CardSpec, img_uri: str, total: int, channel: str) -> str:
    """Cover card: fullbleed image + dark gradient overlay + channel name + swipe CTA."""
    w, h, pad = CARD_WIDTH, CARD_HEIGHT, _PAD_LR
    if img_uri:
        bg = f"background-image:url('{img_uri}');background-size:cover;background-position:center;"
    else:
        bg = "background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);"

    return (
        f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;{bg}">\n'
        # Dark gradient overlay (bottom 60%)
        f'  <div style="position:absolute;bottom:0;left:0;right:0;height:60%;'
        f'background:linear-gradient(transparent 0%,rgba(10,10,10,0.7) 30%,rgba(10,10,10,0.92) 100%);"></div>\n'
        # Channel name (top)
        f'  <div style="position:absolute;top:48px;left:{pad}px;'
        f"font-family:'Noto Sans KR',sans-serif;font-size:28px;font-weight:500;"
        f'color:rgba(255,255,255,0.8);letter-spacing:1px;">{_esc(channel)}</div>\n'
        # Title + body (bottom)
        f'  <div style="position:absolute;bottom:120px;left:{pad}px;right:{pad}px;">\n'
        f'    <div style="font-family:\'Noto Serif KR\',serif;font-size:56px;font-weight:900;'
        f'color:#FFFFFF;line-height:1.2;">{_esc(card.title)}</div>\n'
        f'    {_accent_line(_ACCENT_BLUE)}'
        f'    <div style="font-size:36px;font-weight:300;color:rgba(255,255,255,0.85);'
        f'line-height:1.5;margin-top:8px;">{_esc(card.body)}</div>\n'
        f'  </div>\n'
        # Swipe CTA (very bottom)
        f'  <div style="position:absolute;bottom:40px;left:50%;transform:translateX(-50%);'
        f'font-size:26px;font-weight:400;color:rgba(255,255,255,0.6);">'
        f'\U0001F446 \uc2a4\uc640\uc774\ud504\ud574\uc11c \ud655\uc778\ud558\uc138\uc694</div>\n'
        f'</div>\n'
    )


def _build_content(card: CardSpec, img_uri: str, total: int) -> str:
    """Content card: split layout - left text on dark navy, right image."""
    w, h, pad = CARD_WIDTH, CARD_HEIGHT, _PAD_LR
    # Left side background alternates between navy and charcoal
    bg_color = "#0f1923" if card.index % 2 == 0 else "#1a1a2e"

    # Right side: image or gradient fallback
    if img_uri:
        right_bg = f"background-image:url('{img_uri}');background-size:cover;background-position:center;"
    else:
        right_bg = (
            f"background:linear-gradient(135deg,{bg_color} 0%,"
            f"{'#1e3a5f' if bg_color == '#0f1923' else '#2d2d4e'} 100%);"
        )

    return (
        f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;display:flex;">\n'
        # Left text panel (48%)
        f'  <div style="width:48%;background:{bg_color};padding:80px {pad}px;'
        f'display:flex;flex-direction:column;justify-content:center;position:relative;">\n'
        f'    <div style="font-family:\'Noto Serif KR\',serif;font-size:44px;font-weight:900;'
        f'color:#FAFAFA;line-height:1.25;">{_esc(card.title)}</div>\n'
        f'    {_accent_line(_ACCENT_BLUE)}'
        f'    <div style="font-size:34px;font-weight:300;color:rgba(250,250,250,0.8);'
        f'line-height:1.55;">{_esc(card.body)}</div>\n'
        f'    {_page_num_html(card.index, total, "rgba(250,250,250,0.3)")}'
        f'  </div>\n'
        # Right image panel (52%)
        f'  <div style="width:52%;{right_bg}"></div>\n'
        f'</div>\n'
    )


def _build_tip(card: CardSpec, total: int) -> str:
    """Tip/highlight card: gold-orange gradient, big emoji, centered text."""
    w, h, pad = CARD_WIDTH, CARD_HEIGHT, _PAD_LR

    return (
        f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;'
        f'display:flex;flex-direction:column;justify-content:center;align-items:center;'
        f'text-align:center;padding:{pad}px;'
        f'background:linear-gradient(135deg,#f7971e 0%,#ffd200 100%);">\n'
        # Title (may contain emoji)
        f'  <div style="font-family:\'Noto Serif KR\',serif;font-size:52px;font-weight:900;'
        f'color:#2a1a00;line-height:1.25;">{_esc(card.title)}</div>\n'
        f'  {_accent_line("#2a1a00", centered=True)}'
        f'  <div style="font-size:36px;font-weight:400;color:#3d2800;'
        f'line-height:1.55;">{_esc(card.body)}</div>\n'
        f'  {_page_num_html(card.index, total, "rgba(42,26,0,0.3)")}'
        f'</div>\n'
    )


def _build_closing(card: CardSpec, total: int) -> str:
    """Closing card: dark background, white text, accent line."""
    w, h, pad = CARD_WIDTH, CARD_HEIGHT, _PAD_LR

    return (
        f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;'
        f'display:flex;flex-direction:column;justify-content:center;align-items:center;'
        f'text-align:center;padding:{pad}px;'
        f'background:linear-gradient(180deg,#0a0a0a 0%,#1a1a1a 100%);">\n'
        f'  <div style="font-family:\'Noto Serif KR\',serif;font-size:52px;font-weight:900;'
        f'color:#FAFAFA;line-height:1.3;">{_esc(card.title)}</div>\n'
        f'  {_accent_line(_ACCENT_BLUE, centered=True)}'
        f'  <div style="font-size:36px;font-weight:300;color:rgba(250,250,250,0.8);'
        f'line-height:1.6;">{_esc(card.body)}</div>\n'
        f'  {_page_num_html(card.index, total, "rgba(250,250,250,0.3)")}'
        f'</div>\n'
    )


def _build_cta(card: CardSpec, total: int, channel: str) -> str:
    """CTA card: blue gradient, channel name, YouTube link prompt."""
    w, h, pad = CARD_WIDTH, CARD_HEIGHT, _PAD_LR

    return (
        f'<div style="width:{w}px;height:{h}px;position:relative;overflow:hidden;'
        f'display:flex;flex-direction:column;justify-content:center;align-items:center;'
        f'text-align:center;padding:{pad}px;'
        f'background:linear-gradient(135deg,#1a6cf5 0%,#0a3d91 100%);">\n'
        # Channel name
        f'  <div style="font-size:30px;font-weight:500;color:rgba(255,255,255,0.7);'
        f'letter-spacing:1px;margin-bottom:32px;">{_esc(channel)}</div>\n'
        # Title
        f'  <div style="font-family:\'Noto Serif KR\',serif;font-size:52px;font-weight:900;'
        f'color:#FFFFFF;line-height:1.3;">{_esc(card.title)}</div>\n'
        f'  {_accent_line("#FFFFFF", centered=True)}'
        # Body
        f'  <div style="font-size:36px;font-weight:300;color:rgba(255,255,255,0.9);'
        f'line-height:1.55;">{_esc(card.body)}</div>\n'
        # Bottom CTA
        f'  <div style="position:absolute;bottom:48px;left:50%;transform:translateX(-50%);'
        f'font-size:26px;font-weight:400;color:rgba(255,255,255,0.6);">'
        f'\U0001F446 \ud504\ub85c\ud544 \ub9c1\ud06c \ud074\ub9ad</div>\n'
        f'  {_page_num_html(card.index, total, "rgba(255,255,255,0.3)")}'
        f'</div>\n'
    )


# ---------------------------------------------------------------------------
# Main HTML builder
# ---------------------------------------------------------------------------

def build_card_html(
    card: CardSpec,
    image_path: str | None,
    total: int,
) -> str:
    """Build a complete single-card HTML page based on card_type."""
    settings = get_settings()
    channel = settings.channel_name

    img_uri = ""
    if image_path:
        img_uri = _image_to_data_uri(image_path)

    ct = card.card_type

    if ct == "cover":
        body = _build_cover(card, img_uri, total, channel)
    elif ct == "content":
        body = _build_content(card, img_uri, total)
    elif ct == "tip":
        body = _build_tip(card, total)
    elif ct == "closing":
        body = _build_closing(card, total)
    elif ct == "cta":
        body = _build_cta(card, total, channel)
    else:
        # Fallback: treat unknown as content
        body = _build_content(card, img_uri, total)

    return _wrap_html(body)


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

        # 3. Generate background images (type-aware)
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
            card_type = item.get("card_type", "content")
            if card_type not in _VALID_CARD_TYPES:
                card_type = "content"
            cards.append(CardSpec(
                index=item.get("index", len(cards) + 1),
                title=item.get("title", ""),
                body=item.get("body", ""),
                layout=layout,
                image_prompt=item.get("image_prompt", ""),
                card_type=card_type,
            ))

        return cards

    # ------------------------------------------------------------------
    # Stage 3: Image generation (type-aware strategy)
    # ------------------------------------------------------------------

    async def _generate_images(
        self, cards: list[CardSpec],
    ) -> dict[int, str]:
        """Generate images based on card type.

        - cover: 2K cinematic (always attempted)
        - content: 1K editorial (max 4 images)
        - tip/closing/cta: no image
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="card_img_"))
        image_map: dict[int, str] = {}

        # Cover image first (high priority)
        cover_cards = [c for c in cards if c.card_type == "cover" and c.image_prompt]
        for card in cover_cards:
            dest = temp_dir / f"card_{card.index:02d}.png"
            result = await self._gen_single_image(card.image_prompt, dest, card.index)
            if result:
                image_map[card.index] = result

        # Content images in parallel batches of 3 (max 4 total)
        content_cards = [
            c for c in cards
            if c.card_type == "content" and c.image_prompt
        ][:4]

        if content_cards:
            batch_size = 3
            for i in range(0, len(content_cards), batch_size):
                batch = content_cards[i:i + batch_size]
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
                    card_type=card.card_type,
                    path=str(png_path),
                )

            await browser.close()

        return png_paths
