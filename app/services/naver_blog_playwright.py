"""Naver Blog posting via Playwright browser automation.

Uses playwright-stealth to bypass bot detection since
Naver Blog Write API has been officially deprecated.

Supports structured content blocks (headings, paragraphs,
images, quotes, dividers, links) via SmartEditor integration.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import tempfile
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import Page, async_playwright

from app.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-infobars",
    "--no-first-run",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

_ANTI_DETECT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
  get: () => ['ko-KR', 'ko', 'en-US', 'en'],
});
window.chrome = { runtime: {} };
"""

_VIEWPORT = {"width": 1920, "height": 1080}

# ---------------------------------------------------------------------------
# Human-like motion helpers (module level)
# ---------------------------------------------------------------------------


def _random_delay(low: int = 3, high: int = 30) -> int:
    """Return a random delay in milliseconds."""
    return random.randint(low, high)


def _bezier_curve(
    sx: float, sy: float, ex: float, ey: float, steps: int = 18,
) -> list[tuple[float, float]]:
    """Generate quadratic bezier curve points between two positions."""
    cx = (sx + ex) / 2 + random.uniform(-80, 80)
    cy = (sy + ey) / 2 + random.uniform(-80, 80)
    points: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * ex
        y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ey
        points.append((x, y))
    return points


# ---------------------------------------------------------------------------
# NaverBlogPlaywright
# ---------------------------------------------------------------------------


class NaverBlogPlaywright:
    """Automate Naver Blog posting via headless-capable Playwright."""

    def __init__(
        self,
        blog_id: str | None = None,
        session_path: str | None = None,
    ) -> None:
        settings = get_settings()
        self.blog_id = blog_id if blog_id is not None else (settings.naver_blog_id or "")
        self.session_path = Path(
            session_path if session_path is not None else settings.naver_session_path,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def has_session(self) -> bool:
        """Check whether a saved session file exists."""
        return self.session_path.exists()

    async def setup_session(self) -> None:
        """Open a visible browser for the user to log in manually.

        After login is detected the session state is saved to
        *session_path* for later reuse.  Session is **not** saved if
        login is not confirmed within the timeout.
        """
        from playwright_stealth import Stealth

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                slow_mo=50,
                args=_BROWSER_ARGS,
            )
            context = await browser.new_context(
                viewport=_VIEWPORT,
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                user_agent=_USER_AGENT,
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            await page.add_init_script(_ANTI_DETECT_SCRIPT)

            await page.goto(
                "https://nid.naver.com/nidlogin.login",
                wait_until="domcontentloaded",
            )
            logger.info("naver_login_browser_opened")

            _LOGIN_PATHS = ("nidlogin", "/nidlogin.login")
            logged_in = False
            for tick in range(300):
                await page.wait_for_timeout(1000)
                try:
                    url = page.url
                    if "naver.com" in url and not any(p in url for p in _LOGIN_PATHS):
                        logged_in = True
                        break
                    cookies = await context.cookies("https://naver.com")
                    if any(c["name"] == "NID_AUT" for c in cookies):
                        logged_in = True
                        break
                except Exception:
                    break
                if tick % 30 == 0 and tick > 0:
                    logger.info("naver_login_waiting", elapsed_seconds=tick)

            if not logged_in:
                logger.warning("naver_login_timeout")
                await browser.close()
                return

            try:
                await page.goto(
                    "https://blog.naver.com/",
                    wait_until="domcontentloaded",
                    timeout=15_000,
                )
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(self.session_path))
            logger.info("naver_session_saved", path=str(self.session_path))
            await browser.close()

    # ------------------------------------------------------------------
    # Human-like actions
    # ------------------------------------------------------------------

    async def _human_move(self, page: Page, x: float, y: float) -> None:
        """Move mouse along a bezier curve to (x, y)."""
        try:
            current = await page.evaluate("[window._mx||640, window._my||400]")
            sx, sy = current[0], current[1]
        except Exception:
            sx, sy = 640.0, 400.0

        points = _bezier_curve(sx, sy, x, y)
        for px, py in points:
            await page.mouse.move(px, py)
            await page.wait_for_timeout(random.randint(5, 15))

        # Track position for next call
        await page.evaluate(f"window._mx={x}; window._my={y};")
        # Hover pause
        await page.wait_for_timeout(random.randint(50, 150))

    async def _human_click(self, page: Page, x: float, y: float) -> None:
        """Move mouse to (x, y) with bezier curve then click."""
        await self._human_move(page, x, y)
        await page.mouse.click(x, y)
        await page.wait_for_timeout(random.randint(100, 300))

    async def _human_click_element(self, page: Page, el: Any) -> None:
        """Click a Playwright element handle with human-like motion."""
        try:
            box = await el.bounding_box()
            if box:
                cx = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
                cy = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
                await self._human_click(page, cx, cy)
                return
        except Exception:
            pass
        await el.click()
        await page.wait_for_timeout(random.randint(100, 300))

    async def _human_type(self, page: Page, text: str) -> None:
        """Type text with human-like timing and occasional typos."""
        words = text.split(" ")
        for wi, word in enumerate(words):
            if wi > 0:
                await page.keyboard.type(" ")
                await page.wait_for_timeout(random.randint(50, 150))

            # 5% chance of typo (only on ASCII words > 2 chars)
            if (
                random.random() < 0.05
                and len(word) > 2
                and word.isascii()
                and word.isalpha()
            ):
                typo_char = random.choice("abcdefghijklmnop")
                pos = random.randint(1, len(word) - 1)
                wrong = word[:pos] + typo_char + word[pos:]
                await page.keyboard.type(wrong, delay=random.randint(40, 90))
                await page.wait_for_timeout(random.randint(150, 250))
                for _ in range(len(wrong)):
                    await page.keyboard.press("Backspace")
                await page.wait_for_timeout(random.randint(80, 200))

            await page.keyboard.type(word, delay=random.randint(40, 100))

            # Sentence-end pause
            if word and word[-1] in ".!?":
                await page.wait_for_timeout(random.randint(300, 800))

    async def _human_scroll(self, page: Page, total_px: int) -> None:
        """Scroll gradually in small increments."""
        direction = 1 if total_px > 0 else -1
        remaining = abs(total_px)
        while remaining > 0:
            step = min(remaining, random.randint(80, 180))
            await page.mouse.wheel(0, step * direction)
            remaining -= step
            await page.wait_for_timeout(random.randint(40, 90))

    async def _random_wait(self, page: Page, low: int = 1000, high: int = 3000) -> None:
        """Wait a random duration (simulates human pause)."""
        await page.wait_for_timeout(random.randint(low, high))

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------

    async def post(
        self,
        title: str,
        content: str | list[dict[str, Any]],
        *,
        images: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write and publish a blog post.

        Args:
            title: Blog post title.
            content: Either a plain-text string (sections separated by
                ``\\n\\n``) or a list of structured content blocks::

                    [
                        {"type": "heading2", "text": "..."},
                        {"type": "paragraph", "text": "..."},
                        {"type": "image", "url": "...", "caption": "..."},
                        {"type": "quote", "text": "..."},
                        {"type": "divider"},
                        {"type": "link", "text": "...", "url": "..."},
                    ]

            images: Image file paths or URLs (plain-text mode only).
            tags: Hashtag strings (without ``#``).

        Returns:
            Dict with ``success``, ``url``, and optional ``error``.
        """
        if not self.has_session():
            return {"success": False, "error": "No session file. Run setup_session() first."}
        if not self.blog_id:
            return {"success": False, "error": "NAVER_BLOG_ID not configured."}

        from playwright_stealth import Stealth

        # Resolve images for plain-text mode
        local_images: list[Path] = []
        temp_dir: str | None = None
        if isinstance(content, str) and images:
            temp_dir = tempfile.mkdtemp(prefix="naver_blog_")
            for i, img in enumerate(images):
                try:
                    resolved = await self._resolve_image(img, Path(temp_dir), i)
                    if resolved:
                        local_images.append(resolved)
                except Exception as exc:
                    logger.warning("image_resolve_failed", index=i, error=str(exc))

        # For structured content, pre-download images in blocks
        block_temp_dir: str | None = None
        if isinstance(content, list):
            block_temp_dir = tempfile.mkdtemp(prefix="naver_block_img_")
            content = await self._resolve_block_images(content, Path(block_temp_dir))

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=False,
                    slow_mo=60,
                    args=_BROWSER_ARGS,
                )
                context = await browser.new_context(
                    storage_state=str(self.session_path),
                    viewport=_VIEWPORT,
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                    user_agent=_USER_AGENT,
                )
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                await page.add_init_script(_ANTI_DETECT_SCRIPT)

                # Step 1: Open editor + random wait
                await self._open_editor(page)
                await self._random_wait(page, 1000, 2500)

                # Step 2: Type title
                await self._input_title(page, title)

                # Step 3: Move to body area
                await page.keyboard.press("Tab")
                await self._random_wait(page, 400, 800)

                # Step 4: Write content
                if isinstance(content, list):
                    await self._write_blocks(page, content)
                else:
                    sections = [s for s in content.split("\n\n") if s.strip()]
                    await self._write_body(page, sections, local_images)

                # Step 5: Hashtags
                if tags:
                    await self._input_hashtags(page, tags)

                # Step 6: Publish
                published = await self._publish(page)

                await page.wait_for_timeout(3000)
                final_url = page.url

                success = (
                    published
                    and ("PostView" in final_url or "logNo" in final_url)
                )

                await context.storage_state(path=str(self.session_path))
                await browser.close()

                if success:
                    logger.info("naver_blog_published", url=final_url)
                    return {"success": True, "url": final_url}
                else:
                    logger.warning("naver_blog_publish_uncertain", url=final_url)
                    return {
                        "success": True,
                        "url": final_url,
                        "warning": "Publish clicked but PostView URL not confirmed.",
                    }

        except Exception as exc:
            logger.error("naver_blog_post_failed", error=str(exc))
            return {"success": False, "error": str(exc)}
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            if block_temp_dir:
                shutil.rmtree(block_temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    async def _resolve_image(
        self, img: str, temp_dir: Path, index: int,
    ) -> Path | None:
        """If *img* is a URL download it; if a path return as-is."""
        path = Path(img)
        if path.exists():
            return path

        if img.startswith(("http://", "https://")):
            dest = temp_dir / f"img_{index}.jpg"
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(img)
                if resp.status_code == 200:
                    dest.write_bytes(resp.content)
                    return dest
        return None

    async def _resolve_block_images(
        self,
        blocks: list[dict[str, Any]],
        temp_dir: Path,
    ) -> list[dict[str, Any]]:
        """Download URLs in image blocks to local temp files."""
        resolved: list[dict[str, Any]] = []
        img_idx = 0
        for block in blocks:
            if block.get("type") == "image" and block.get("url"):
                url = block["url"]
                try:
                    local = await self._resolve_image(url, temp_dir, img_idx)
                    if local:
                        new_block = {**block, "_local_path": str(local)}
                        resolved.append(new_block)
                        img_idx += 1
                        continue
                except Exception as exc:
                    logger.warning("block_image_resolve_failed", error=str(exc))
                # Keep block but without local path (will be skipped)
                resolved.append(block)
            else:
                resolved.append(block)
        return resolved

    # ------------------------------------------------------------------
    # Editor navigation
    # ------------------------------------------------------------------

    async def _open_editor(self, page: Page) -> None:
        """Navigate to the blog editor and dismiss popups."""
        await page.goto(
            f"https://blog.naver.com/{self.blog_id}/postwrite",
            timeout=30_000,
        )
        await page.wait_for_timeout(5000)

        # Dismiss "resume draft?" popup
        try:
            cancel = await page.query_selector(".se-popup-button-cancel")
            if cancel:
                await self._human_click_element(page, cancel)
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        logger.info("naver_editor_opened")

    async def _input_title(self, page: Page, title: str) -> None:
        """Click the title area and type with human-like motion."""
        title_el = await page.query_selector(
            ".se-documentTitle .se-text-paragraph",
        )
        if title_el:
            await self._human_click_element(page, title_el)
        else:
            await self._human_click(page, 640, 130)
        await page.wait_for_timeout(300)
        await self._human_type(page, title)
        logger.info("naver_title_entered", title=title[:50])

    async def _upload_one_image(self, page: Page, image_path: Path) -> bool:
        """Upload a single image via the editor toolbar button."""
        try:
            image_btn = await page.query_selector('button[data-name="image"]')
            if not image_btn:
                return False

            await self._human_click_element(page, image_btn)
            await page.wait_for_timeout(500)

            # Wait for file chooser dialog
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                # Some editors need a second click on "PC upload" option
                pc_btn = await page.query_selector(
                    'button[class*="pc_upload"], li[data-type="local"] button',
                )
                if pc_btn:
                    await pc_btn.click()
                else:
                    await image_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))
            await page.wait_for_timeout(3000)
            return True
        except Exception as exc:
            logger.warning("naver_image_upload_failed", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Plain-text body (backward compat)
    # ------------------------------------------------------------------

    async def _write_body(
        self,
        page: Page,
        sections: list[str],
        images: list[Path],
    ) -> None:
        """Alternate between uploading images and typing text sections."""
        max_loop = max(len(images), len(sections))
        uploaded = 0

        for i in range(max_loop):
            if i < len(images):
                if await self._upload_one_image(page, images[i]):
                    uploaded += 1

            if i < len(sections):
                await self._type_section(page, sections[i])
                await self._random_wait(page, 200, 500)

        logger.info(
            "naver_body_written",
            sections=len(sections),
            images_uploaded=uploaded,
        )

    async def _type_section(self, page: Page, text: str) -> None:
        """Type a text section line by line with realistic delays."""
        lines = text.split("\n")
        for line in lines:
            if line.strip() == "":
                await page.keyboard.press("Enter")
            else:
                await self._human_type(page, line)
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(random.randint(30, 80))
        await page.keyboard.press("Enter")

    # ------------------------------------------------------------------
    # Structured content blocks
    # ------------------------------------------------------------------

    async def _write_blocks(self, page: Page, blocks: list[dict[str, Any]]) -> None:
        """Process structured content blocks sequentially."""
        stats: dict[str, int] = {}
        for block in blocks:
            btype = block.get("type", "paragraph")
            try:
                if btype in ("heading2", "heading3"):
                    await self._block_heading(page, block.get("text", ""), btype)
                elif btype == "paragraph":
                    await self._block_paragraph(page, block.get("text", ""))
                elif btype == "image":
                    await self._block_image(page, block)
                elif btype == "quote":
                    await self._block_quote(page, block.get("text", ""))
                elif btype == "divider":
                    await self._block_divider(page)
                elif btype == "link":
                    await self._block_link(
                        page, block.get("text", ""), block.get("url", ""),
                    )
                else:
                    # Unknown type — treat as paragraph
                    await self._block_paragraph(page, block.get("text", ""))

                stats[btype] = stats.get(btype, 0) + 1
            except Exception as exc:
                logger.warning("block_failed", type=btype, error=str(exc))

            await self._random_wait(page, 200, 600)

        logger.info("naver_blocks_written", stats=stats)

    async def _block_heading(self, page: Page, text: str, level: str) -> None:
        """Insert a heading using bold + font size increase."""
        if not text:
            return

        # Bold on
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(100)

        # For heading2, try to apply larger font size via toolbar
        if level == "heading2":
            await self._try_font_size(page, increase=3)
        elif level == "heading3":
            await self._try_font_size(page, increase=1)

        await self._human_type(page, text)
        await page.keyboard.press("Enter")

        # Bold off and reset font size
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(100)

        # Reset font size
        if level in ("heading2", "heading3"):
            await self._try_reset_font_size(page)

        await page.keyboard.press("Enter")

    async def _try_font_size(self, page: Page, increase: int = 1) -> None:
        """Try to increase font size via toolbar button."""
        try:
            size_up = await page.query_selector(
                'button[data-name="fontSizeUp"], button[class*="font_size_up"]',
            )
            if size_up:
                for _ in range(increase):
                    await size_up.click()
                    await page.wait_for_timeout(100)
        except Exception:
            pass

    async def _try_reset_font_size(self, page: Page) -> None:
        """Try to reset font size via toolbar."""
        try:
            size_down = await page.query_selector(
                'button[data-name="fontSizeDown"], button[class*="font_size_down"]',
            )
            if size_down:
                for _ in range(5):
                    await size_down.click()
                    await page.wait_for_timeout(50)
        except Exception:
            pass

    async def _block_paragraph(self, page: Page, text: str) -> None:
        """Type a paragraph with natural typing."""
        if not text:
            return

        # Split into sentences for natural pacing
        sentences = text.replace(". ", ".|").split("|")
        for i, sentence in enumerate(sentences):
            if i > 0:
                await page.keyboard.type(" ")
                await self._random_wait(page, 200, 500)
            await self._human_type(page, sentence.strip())

        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")

    async def _block_image(self, page: Page, block: dict[str, Any]) -> None:
        """Upload an image block (pre-resolved to local path)."""
        local_path = block.get("_local_path")
        if not local_path:
            logger.warning("block_image_no_local_path")
            return

        path = Path(local_path)
        if not path.exists():
            logger.warning("block_image_file_missing", path=local_path)
            return

        uploaded = await self._upload_one_image(page, path)

        # Add caption if present
        caption = block.get("caption")
        if uploaded and caption:
            await page.keyboard.press("Enter")
            await self._human_type(page, caption)
            await page.keyboard.press("Enter")

    async def _block_quote(self, page: Page, text: str) -> None:
        """Insert a quotation block via SmartEditor toolbar."""
        if not text:
            return

        # Try SmartEditor quotation button
        inserted = False
        try:
            quote_btn = await page.query_selector(
                'button[data-name="quotation"]',
            )
            if quote_btn:
                await self._human_click_element(page, quote_btn)
                await page.wait_for_timeout(800)
                inserted = True
        except Exception:
            pass

        if inserted:
            await self._human_type(page, text)
            # Move cursor out of quote block
            await page.keyboard.press("Enter")
            await page.keyboard.press("Enter")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        else:
            # Fallback: plain-text quote style
            for line in text.split("\n"):
                await page.keyboard.type(f"> {line}")
                await page.keyboard.press("Enter")
            await page.keyboard.press("Enter")

    async def _block_divider(self, page: Page) -> None:
        """Insert a horizontal rule via SmartEditor toolbar."""
        try:
            hr_btn = await page.query_selector(
                'button[data-name="horizontalRule"]',
            )
            if hr_btn:
                await self._human_click_element(page, hr_btn)
                await page.wait_for_timeout(500)
                return
        except Exception:
            pass

        # Fallback: visual divider text
        await page.keyboard.type("ㅡ" * 30)
        await page.keyboard.press("Enter")

    async def _block_link(self, page: Page, text: str, url: str) -> None:
        """Insert a link — type text with URL in parentheses as fallback."""
        if not text and not url:
            return

        # Fallback approach: just type "text (url)" since link insertion
        # in SmartEditor requires complex selector chains
        display = text or url
        await self._human_type(page, display)
        if url and text:
            await page.keyboard.type(f" ({url})")
        await page.keyboard.press("Enter")

    # ------------------------------------------------------------------
    # Hashtags & publish
    # ------------------------------------------------------------------

    async def _input_hashtags(self, page: Page, tags: list[str]) -> None:
        """Type hashtags at the end of the post."""
        await page.keyboard.press("Enter")
        hashtag_text = " ".join(f"#{t.replace(' ', '')}" for t in tags)
        await self._human_type(page, hashtag_text)
        logger.info("naver_hashtags_entered", count=len(tags))

    async def _publish(self, page: Page) -> bool:
        """Click publish buttons (header -> confirm dialog)."""
        # Close help panels / tooltips
        for _ in range(3):
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)

        close_selectors = [
            '.help_layer button[class*="close"]',
            '.tooltip button[class*="close"]',
            '.se-help-panel-close-button',
            '.guide_layer button[class*="close"]',
            'button[aria-label="\ub2eb\uae30"]',
            '[class*="close_btn"]',
        ]
        for sel in close_selectors:
            btn = await page.query_selector(sel)
            if btn:
                try:
                    await btn.click()
                except Exception:
                    pass
                await page.wait_for_timeout(200)

        await self._human_scroll(page, -2000)
        await page.wait_for_timeout(500)

        # Click header publish button
        header_btn = await page.query_selector(
            'button[class*="publish_btn"], header button[class*="publish"]',
        )
        if header_btn:
            await self._human_click_element(page, header_btn)
        else:
            await self._human_click(page, 1810, 22)
        await page.wait_for_timeout(2000)

        # Click final confirm button in publish dialog
        confirm_selectors = [
            'button[class*="confirm_btn"]',
            'button[class*="btn_publish"]',
            '.publish_layer button[class*="confirm"]',
        ]
        for sel in confirm_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await self._human_click_element(page, btn)
                    await page.wait_for_timeout(5000)
                    return True
            except Exception:
                continue

        # Try finding button by text content
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = await btn.text_content()
            if text and "\ubc1c\ud589" in text and "\uc608\uc57d" not in text:
                if await btn.is_visible():
                    await self._human_click_element(page, btn)
                    await page.wait_for_timeout(5000)
                    return True

        # Fallback: coordinate clicks
        await self._human_click(page, 480, 455)
        await page.wait_for_timeout(2000)
        await self._human_click(page, 470, 450)
        await page.wait_for_timeout(3000)
        return True
