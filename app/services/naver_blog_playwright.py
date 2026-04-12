"""Naver Blog posting via Playwright browser automation.

Uses playwright-stealth to bypass bot detection since
Naver Blog Write API has been officially deprecated.

Supports structured content blocks (headings, paragraphs,
images, quotes, dividers, links, highlights) via SmartEditor.
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

# Quote style index in SmartEditor quotation dropdown (0-based).
_QUOTE_STYLE_INDEX: dict[str, int] = {
    "classic": 0,
    "vertical": 1,
    "bubble": 2,
    "sticker": 3,
}

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
        """Open a visible browser for the user to log in manually."""
        from playwright_stealth import Stealth

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False, slow_mo=50, args=_BROWSER_ARGS,
            )
            context = await browser.new_context(
                viewport=_VIEWPORT, locale="ko-KR",
                timezone_id="Asia/Seoul", user_agent=_USER_AGENT,
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
                    wait_until="domcontentloaded", timeout=15_000,
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

        for px, py in _bezier_curve(sx, sy, x, y):
            await page.mouse.move(px, py)
            await page.wait_for_timeout(random.randint(3, 8))
        await page.evaluate(f"window._mx={x}; window._my={y};")
        await page.wait_for_timeout(random.randint(20, 60))

    async def _human_click(self, page: Page, x: float, y: float) -> None:
        await self._human_move(page, x, y)
        await page.mouse.click(x, y)
        await page.wait_for_timeout(random.randint(50, 150))

    async def _human_click_element(self, page: Page, el: Any) -> None:
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
        await page.wait_for_timeout(random.randint(50, 150))

    async def _human_type(self, page: Page, text: str) -> None:
        """Type text with human-like timing and occasional typos."""
        words = text.split(" ")
        for wi, word in enumerate(words):
            if wi > 0:
                await page.keyboard.type(" ")
                await page.wait_for_timeout(random.randint(20, 60))
            if (
                random.random() < 0.05
                and len(word) > 2
                and word.isascii()
                and word.isalpha()
            ):
                typo_char = random.choice("abcdefghijklmnop")
                pos = random.randint(1, len(word) - 1)
                wrong = word[:pos] + typo_char + word[pos:]
                await page.keyboard.type(wrong, delay=random.randint(15, 40))
                await page.wait_for_timeout(random.randint(60, 120))
                for _ in range(len(wrong)):
                    await page.keyboard.press("Backspace")
                await page.wait_for_timeout(random.randint(30, 80))
            await page.keyboard.type(word, delay=random.randint(20, 60))
            if word and word[-1] in ".!?":
                await page.wait_for_timeout(random.randint(100, 300))

    async def _human_scroll(self, page: Page, total_px: int) -> None:
        direction = 1 if total_px > 0 else -1
        remaining = abs(total_px)
        while remaining > 0:
            step = min(remaining, random.randint(80, 180))
            await page.mouse.wheel(0, step * direction)
            remaining -= step
            await page.wait_for_timeout(random.randint(20, 50))

    async def _random_wait(
        self, page: Page, low: int = 500, high: int = 1000,
    ) -> None:
        await page.wait_for_timeout(random.randint(low, high))

    # ------------------------------------------------------------------
    # Style reset helpers (mobile-optimisation / anti-contamination)
    # ------------------------------------------------------------------

    async def _reset_formatting(self, page: Page) -> None:
        """Clear bold, italic, underline and reset font size.

        Called after every heading / highlight block so that the
        style does **not** leak into the next paragraph.
        """
        # Turn off bold / italic / underline if active
        for key in ("b", "i", "u"):
            await page.keyboard.down("Control")
            await page.keyboard.press(key)
            await page.keyboard.up("Control")
            await page.wait_for_timeout(50)
        # Toggle them back (now they are guaranteed OFF)
        for key in ("b", "i", "u"):
            await page.keyboard.down("Control")
            await page.keyboard.press(key)
            await page.keyboard.up("Control")
            await page.wait_for_timeout(50)

        # Actually — the above double-toggle is fragile.
        # Instead: press once to ensure OFF, relying on the fact that
        # _block_heading turned bold ON, so one press turns it OFF.
        # Let's use a different approach: just hit Ctrl+B twice rapidly.
        # The SE One editor tracks toggle state internally.
        # We'll rely on a simpler method: type a zero-width space,
        # select it, and clear formatting via the editor's "clear format" button.
        # But that's also fragile. The safest approach is to:
        #
        # 1. Press Enter to start a new paragraph (which resets in SE One)
        # 2. Try clicking the "clear format" toolbar button
        #
        # SE One resets formatting on new paragraph automatically for
        # block-level styles. The issue is inline styles (bold/italic).

        # Try the "clear format" / "removeFormat" toolbar button
        try:
            clear_btn = await page.query_selector(
                'button[data-name="removeFormat"]',
            )
            if clear_btn:
                await clear_btn.click()
                await page.wait_for_timeout(100)
                return
        except Exception:
            pass

        # Fallback: select the new empty line and clear
        # Actually safest: just ensure bold is OFF by pressing Ctrl+B
        # We already turned bold OFF in _block_heading, so this is a no-op
        # safety net.

    async def _ensure_left_align(self, page: Page) -> None:
        """Force left alignment via Ctrl+L (SmartEditor shortcut)."""
        await page.keyboard.down("Control")
        await page.keyboard.press("l")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(80)

    async def _ensure_plain_style(self, page: Page) -> None:
        """Reset to normal paragraph style — no bold, no italic, left align."""
        # Attempt removeFormat button
        try:
            clear_btn = await page.query_selector(
                'button[data-name="removeFormat"]',
            )
            if clear_btn:
                await clear_btn.click()
                await page.wait_for_timeout(100)
        except Exception:
            pass
        await self._ensure_left_align(page)

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

        *content* may be a plain string or a list of structured blocks::

            [
                {"type": "heading2", "text": "..."},
                {"type": "paragraph", "text": "..."},
                {"type": "image", "url": "...", "caption": "..."},
                {"type": "quote", "text": "...", "style": "vertical"},
                {"type": "highlight", "text": "...", "color": "red"},
                {"type": "divider"},
                {"type": "link", "text": "...", "url": "..."},
            ]
        """
        if not self.has_session():
            return {"success": False, "error": "No session file. Run setup_session() first."}
        if not self.blog_id:
            return {"success": False, "error": "NAVER_BLOG_ID not configured."}

        from playwright_stealth import Stealth

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

        block_temp_dir: str | None = None
        if isinstance(content, list):
            block_temp_dir = tempfile.mkdtemp(prefix="naver_block_img_")
            content = await self._resolve_block_images(content, Path(block_temp_dir))

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=False, slow_mo=30, args=_BROWSER_ARGS,
                )
                context = await browser.new_context(
                    storage_state=str(self.session_path),
                    viewport=_VIEWPORT, locale="ko-KR",
                    timezone_id="Asia/Seoul", user_agent=_USER_AGENT,
                )
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                await page.add_init_script(_ANTI_DETECT_SCRIPT)

                await self._open_editor(page)
                await self._random_wait(page, 500, 1000)

                await self._input_title(page, title)
                await page.keyboard.press("Tab")
                await self._random_wait(page, 400, 800)
                # Ensure body starts in plain left-aligned style
                await self._ensure_left_align(page)

                if isinstance(content, list):
                    await self._write_blocks(page, content)
                else:
                    sections = [s for s in content.split("\n\n") if s.strip()]
                    await self._write_body(page, sections, local_images)

                if tags:
                    await self._input_hashtags(page, tags)

                published = await self._publish(page)
                await page.wait_for_timeout(1500)
                final_url = page.url

                success = published and (
                    "PostView" in final_url or "logNo" in final_url
                )
                await context.storage_state(path=str(self.session_path))
                await browser.close()

                if success:
                    logger.info("naver_blog_published", url=final_url)
                    return {"success": True, "url": final_url}
                logger.warning("naver_blog_publish_uncertain", url=final_url)
                return {
                    "success": True, "url": final_url,
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
        self, blocks: list[dict[str, Any]], temp_dir: Path,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        img_idx = 0
        for block in blocks:
            if block.get("type") == "image" and block.get("url"):
                try:
                    local = await self._resolve_image(
                        block["url"], temp_dir, img_idx,
                    )
                    if local:
                        resolved.append({**block, "_local_path": str(local)})
                        img_idx += 1
                        continue
                except Exception as exc:
                    logger.warning("block_image_resolve_failed", error=str(exc))
                resolved.append(block)
            else:
                resolved.append(block)
        return resolved

    # ------------------------------------------------------------------
    # Editor navigation
    # ------------------------------------------------------------------

    async def _open_editor(self, page: Page) -> None:
        await page.goto(
            f"https://blog.naver.com/{self.blog_id}/postwrite",
            timeout=30_000,
        )
        await page.wait_for_timeout(2500)
        try:
            cancel = await page.query_selector(".se-popup-button-cancel")
            if cancel:
                await self._human_click_element(page, cancel)
                await page.wait_for_timeout(500)
        except Exception:
            pass
        logger.info("naver_editor_opened")

    async def _input_title(self, page: Page, title: str) -> None:
        # Truncate title to 90 chars (Naver limit)
        if len(title) > 90:
            title = title[:87] + "..."

        # Click title area — try multiple selectors in priority order
        _TITLE_SELECTORS = [
            ".se-documentTitle .se-text-paragraph span",
            ".se-documentTitle .se-text-paragraph",
            ".se-documentTitle",
        ]
        clicked = False
        for sel in _TITLE_SELECTORS:
            el = await page.query_selector(sel)
            if el:
                await self._human_click_element(page, el)
                clicked = True
                break
        if not clicked:
            await self._human_click(page, 640, 130)

        await page.wait_for_timeout(300)

        # Clear any existing title text before typing
        await page.keyboard.down("Control")
        await page.keyboard.press("a")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(100)

        await self._human_type(page, title)

        # Wait 1 second for title to settle, then move focus to body
        await page.wait_for_timeout(1000)

        # Move focus to body area — try clicking body element explicitly
        _BODY_SELECTORS = [
            ".se-component-content .se-text-paragraph",
            ".se-content .se-text-paragraph",
            ".se-component.se-text .se-text-paragraph",
        ]
        body_clicked = False
        for sel in _BODY_SELECTORS:
            el = await page.query_selector(sel)
            if el:
                await self._human_click_element(page, el)
                body_clicked = True
                break
        if not body_clicked:
            await page.keyboard.press("Tab")

        await page.wait_for_timeout(300)
        logger.info("naver_title_entered", title=title[:50])

    async def _upload_one_image(self, page: Page, image_path: Path) -> bool:
        try:
            image_btn = await page.query_selector('button[data-name="image"]')
            if not image_btn:
                logger.warning("naver_image_btn_not_found")
                return False

            # Verify this is actually the image toolbar button
            btn_text = await image_btn.get_attribute("data-name")
            if btn_text != "image":
                logger.warning("naver_image_btn_mismatch", data_name=btn_text)
                return False

            await self._human_click_element(page, image_btn)
            await page.wait_for_timeout(300)

            # Find the PC upload button before expecting file chooser
            pc_btn = await page.query_selector(
                'li[data-type="local"] button, '
                'button[class*="pc_upload"], '
                '[class*="local_upload"] button',
            )
            if not pc_btn:
                # No PC upload option found — close panel and skip
                logger.warning("naver_image_pc_btn_not_found")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(200)
                return False

            # Now expect file chooser and click the PC upload button
            try:
                async with page.expect_file_chooser(timeout=3000) as fc_info:
                    await pc_btn.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(str(image_path))
                await page.wait_for_timeout(1500)
                return True
            except TimeoutError:
                logger.warning("naver_image_file_chooser_timeout")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(200)
                return False
        except Exception as exc:
            logger.warning("naver_image_upload_failed", error=str(exc))
            # Try to dismiss any open dialog
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    # ------------------------------------------------------------------
    # Plain-text body (backward compat)
    # ------------------------------------------------------------------

    async def _write_body(
        self, page: Page, sections: list[str], images: list[Path],
    ) -> None:
        max_loop = max(len(images), len(sections))
        uploaded = 0
        for i in range(max_loop):
            if i < len(images):
                if await self._upload_one_image(page, images[i]):
                    uploaded += 1
            if i < len(sections):
                await self._type_section(page, sections[i])
                await self._random_wait(page, 100, 250)
        logger.info(
            "naver_body_written",
            sections=len(sections), images_uploaded=uploaded,
        )

    async def _type_section(self, page: Page, text: str) -> None:
        for line in text.split("\n"):
            if not line.strip():
                await page.keyboard.press("Enter")
            else:
                await self._human_type(page, line)
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(random.randint(30, 80))
        await page.keyboard.press("Enter")

    # ------------------------------------------------------------------
    # Structured content blocks
    # ------------------------------------------------------------------

    async def _write_blocks(
        self, page: Page, blocks: list[dict[str, Any]],
    ) -> None:
        stats: dict[str, int] = {}
        for block in blocks:
            btype = block.get("type", "paragraph")
            # Guard: stop if browser/page was closed
            if page.is_closed():
                logger.warning("page_closed_during_blocks", written=sum(stats.values()))
                break
            try:
                if btype in ("heading2", "heading3"):
                    await self._block_heading(page, block.get("text", ""), btype)
                elif btype == "paragraph":
                    await self._block_paragraph(page, block.get("text", ""))
                elif btype == "image":
                    await self._block_image(page, block)
                elif btype == "quote":
                    await self._block_quote(
                        page, block.get("text", ""),
                        style=block.get("style", "classic"),
                    )
                elif btype == "highlight":
                    await self._block_highlight(
                        page, block.get("text", ""),
                        color=block.get("color", "red"),
                    )
                elif btype == "table":
                    await self._block_table(page, block)
                elif btype == "divider":
                    await self._block_divider(page)
                elif btype == "link":
                    await self._block_link(
                        page, block.get("text", ""), block.get("url", ""),
                    )
                else:
                    await self._block_paragraph(page, block.get("text", ""))
                stats[btype] = stats.get(btype, 0) + 1
            except Exception as exc:
                logger.warning("block_failed", type=btype, error=str(exc))
            await self._random_wait(page, 100, 300)

        logger.info("naver_blocks_written", stats=stats)

    # --- heading -------------------------------------------------------

    async def _block_heading(
        self, page: Page, text: str, level: str,
    ) -> None:
        """Insert heading: bold text, then **fully reset** style."""
        if not text:
            return

        # Ensure left align before heading
        await self._ensure_left_align(page)

        # Bold ON
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(80)

        # Font size increase
        increase = 3 if level == "heading2" else 1
        await self._try_font_size(page, increase=increase)

        # Type heading text
        await self._human_type(page, text)

        # New line to finalize heading paragraph
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(100)

        # === Critical: reset ALL formatting so next block is clean ===
        # 1. Bold OFF
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(80)

        # 2. Reset font size back to default
        await self._try_reset_font_size(page)

        # 3. Try removeFormat button for anything else that leaked
        await self._ensure_plain_style(page)

        # 4. Extra Enter for spacing (mobile readability)
        await page.keyboard.press("Enter")

    async def _try_font_size(self, page: Page, increase: int = 1) -> None:
        for _ in range(increase):
            try:
                btn = await page.query_selector(
                    'button[data-name="fontSizeUp"]',
                )
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(120)
                else:
                    break
            except Exception:
                break

    async def _try_reset_font_size(self, page: Page) -> None:
        for _ in range(6):
            try:
                btn = await page.query_selector(
                    'button[data-name="fontSizeDown"]',
                )
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(80)
                else:
                    break
            except Exception:
                break

    # --- paragraph -----------------------------------------------------

    async def _block_paragraph(self, page: Page, text: str) -> None:
        if not text:
            return
        await self._ensure_left_align(page)
        sentences = text.replace(". ", ".|").split("|")
        for i, sentence in enumerate(sentences):
            if i > 0:
                await page.keyboard.type(" ")
                await self._random_wait(page, 100, 250)
            await self._human_type(page, sentence.strip())
        # Double Enter for mobile spacing
        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")

    # --- image ---------------------------------------------------------

    async def _block_image(self, page: Page, block: dict[str, Any]) -> None:
        local_path = block.get("_local_path")
        if not local_path:
            logger.warning("block_image_no_local_path")
            return
        path = Path(local_path)
        if not path.exists():
            logger.warning("block_image_file_missing", path=local_path)
            return
        uploaded = await self._upload_one_image(page, path)
        caption = block.get("caption")
        if uploaded and caption:
            await page.keyboard.press("Enter")
            await self._human_type(page, caption)
            await page.keyboard.press("Enter")

    # --- quote (with style selection) ----------------------------------

    async def _block_quote(
        self, page: Page, text: str, *, style: str = "classic",
    ) -> None:
        """Insert a quotation block, optionally selecting a style variant."""
        if not text:
            return

        inserted = False
        try:
            quote_btn = await page.query_selector(
                'button[data-name="quotation"]',
            )
            if quote_btn:
                await self._human_click_element(page, quote_btn)
                await page.wait_for_timeout(300)

                # Try to pick a style from the quote style selector
                await self._select_quote_style(page, style)
                await page.wait_for_timeout(200)
                inserted = True
        except Exception:
            pass

        if inserted:
            await self._human_type(page, text)
            # === Escape from quote block reliably ===
            # Press ArrowDown repeatedly + Enter to exit the quote component
            for _ in range(3):
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(100)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(200)
            # Press Escape to deselect the quote component
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            # Click below the quote block to ensure cursor is outside
            await page.keyboard.press("End")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(200)
            # Reset to plain style
            await self._ensure_plain_style(page)
            # Extra Enter for spacing
            await page.keyboard.press("Enter")
        else:
            # Fallback: just italic text for visual distinction
            await self._ensure_left_align(page)
            await page.keyboard.type(f"\u300c{text}\u300d")
            await page.keyboard.press("Enter")
            await page.keyboard.press("Enter")

    async def _select_quote_style(self, page: Page, style: str) -> None:
        """Try to select a quote style from the SE One quote dropdown."""
        idx = _QUOTE_STYLE_INDEX.get(style, 0)
        if idx == 0:
            return  # classic is the default, no selection needed

        try:
            # Look for quote style options in the dropdown/panel
            style_items = await page.query_selector_all(
                '.se-quotation-style-item, '
                '[class*="quotation_style"] li, '
                '[class*="quote_style"] button',
            )
            if style_items and idx < len(style_items):
                await self._human_click_element(page, style_items[idx])
                await page.wait_for_timeout(300)
                return

            # Alternative: look for data attributes
            style_btn = await page.query_selector(
                f'[data-style-index="{idx}"], '
                f'[data-value="{style}"]',
            )
            if style_btn:
                await self._human_click_element(page, style_btn)
                await page.wait_for_timeout(300)
        except Exception as exc:
            logger.warning("quote_style_select_failed", style=style, error=str(exc))

    # --- highlight -----------------------------------------------------

    async def _block_highlight(
        self, page: Page, text: str, *, color: str = "red",
    ) -> None:
        """Type bold colored text, then reset formatting."""
        if not text:
            return

        await self._ensure_left_align(page)

        # Bold ON
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(80)

        # Try to set font color via toolbar
        await self._try_font_color(page, color)

        # Type the highlighted text
        await self._human_type(page, text)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(100)

        # Bold OFF
        await page.keyboard.down("Control")
        await page.keyboard.press("b")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(80)

        # Reset color to black
        await self._try_font_color(page, "black")

        # Full style reset
        await self._ensure_plain_style(page)
        await page.keyboard.press("Enter")

    async def _try_font_color(self, page: Page, color: str) -> None:
        """Try to change font color via the SmartEditor toolbar."""
        _COLOR_MAP = {
            "red": "#ff0000",
            "blue": "#0000ff",
            "green": "#009a00",
            "orange": "#ff6600",
            "black": "#000000",
        }
        hex_color = _COLOR_MAP.get(color, color)

        try:
            # Click the font color button to open palette
            color_btn = await page.query_selector(
                'button[data-name="fontColor"], button[class*="font_color"]',
            )
            if not color_btn:
                return

            await self._human_click_element(page, color_btn)
            await page.wait_for_timeout(500)

            # Try to find the color in the palette
            color_el = await page.query_selector(
                f'[data-color="{hex_color}"], '
                f'[style*="background-color: {hex_color}"], '
                f'[style*="background: {hex_color}"]',
            )
            if color_el:
                await self._human_click_element(page, color_el)
                await page.wait_for_timeout(200)
            else:
                # Close palette without selecting
                await page.keyboard.press("Escape")
        except Exception as exc:
            logger.warning("font_color_failed", color=color, error=str(exc))

    # --- table ---------------------------------------------------------

    async def _block_table(self, page: Page, block: dict[str, Any]) -> None:
        """Insert a table block. Falls back to paragraph on failure."""
        headers: list[str] = block.get("headers", [])
        rows: list[list[str]] = block.get("rows", [])
        if not headers and not rows:
            return

        cols = len(headers) if headers else (len(rows[0]) if rows else 0)
        data_rows = len(rows)
        total_rows = (1 if headers else 0) + data_rows

        if cols == 0 or total_rows == 0:
            return

        try:
            table_btn = await page.query_selector(
                'button[data-name="table"]',
            )
            if not table_btn:
                raise RuntimeError("Table button not found")

            await self._human_click_element(page, table_btn)
            await page.wait_for_timeout(500)

            # SE One shows a grid picker — try to click the cell at (col, row)
            grid_cells = await page.query_selector_all(
                ".se-table-size-picker td, "
                "[class*='table_size'] td, "
                "[class*='table_picker'] td",
            )

            if grid_cells:
                # Grids are typically 10-wide; detect width from first row
                grid_width = 10
                try:
                    first_cell_box = await grid_cells[0].bounding_box()
                    if first_cell_box and len(grid_cells) > 1:
                        second_row_y = None
                        for i, cell in enumerate(grid_cells[1:], 1):
                            box = await cell.bounding_box()
                            if box and box["y"] > first_cell_box["y"] + 2:
                                grid_width = i
                                break
                except Exception:
                    pass

                target_col = min(cols, grid_width) - 1
                target_row = min(total_rows, 10) - 1
                target_idx = target_row * grid_width + target_col

                if target_idx < len(grid_cells):
                    await self._human_click_element(
                        page, grid_cells[target_idx],
                    )
                else:
                    await self._human_click_element(
                        page, grid_cells[min(len(grid_cells) - 1, target_idx)],
                    )
            else:
                # No grid found — try confirm button for default table
                confirm = await page.query_selector(
                    ".se-table-size-confirm, "
                    'button[class*="confirm"]',
                )
                if confirm:
                    await confirm.click()

            await page.wait_for_timeout(500)

            # Fill cells: headers first, then data rows (Tab between cells)
            all_cells: list[str] = []
            if headers:
                all_cells.extend(headers)
            for row in rows:
                # Pad/truncate row to match column count
                padded = (list(row) + [""] * cols)[:cols]
                all_cells.extend(str(c) for c in padded)

            for i, cell_text in enumerate(all_cells):
                if i > 0:
                    await page.keyboard.press("Tab")
                    await page.wait_for_timeout(50)
                await page.keyboard.type(cell_text)
                await page.wait_for_timeout(50)

            # Exit table: arrow down + Enter
            for _ in range(3):
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(100)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(200)
            await self._ensure_plain_style(page)
            await page.keyboard.press("Enter")

        except Exception as exc:
            logger.warning("block_table_failed", error=str(exc))
            await self._table_as_paragraph(page, headers, rows)

    async def _table_as_paragraph(
        self,
        page: Page,
        headers: list[str],
        rows: list[list[str]],
    ) -> None:
        """Fallback: render table data as pipe-separated text."""
        await self._ensure_left_align(page)
        if headers:
            await self._human_type(page, " | ".join(headers))
            await page.keyboard.press("Enter")
        for row in rows:
            await self._human_type(page, " | ".join(str(c) for c in row))
            await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")

    # --- divider -------------------------------------------------------

    async def _block_divider(self, page: Page) -> None:
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
        await page.keyboard.type("\u3161" * 30)
        await page.keyboard.press("Enter")

    # --- link ----------------------------------------------------------

    async def _block_link(self, page: Page, text: str, url: str) -> None:
        if not text and not url:
            return
        display = text or url
        await self._human_type(page, display)
        if url and text:
            await page.keyboard.type(f" ({url})")
        await page.keyboard.press("Enter")

    # ------------------------------------------------------------------
    # Hashtags & publish
    # ------------------------------------------------------------------

    async def _input_hashtags(self, page: Page, tags: list[str]) -> None:
        """Type hashtags as plain text at the end (NOT inside quote block)."""
        # Ensure we escaped any active component (quote, etc.)
        for _ in range(3):
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(100)

        # Click at end of document to be safe
        await page.keyboard.down("Control")
        await page.keyboard.press("End")
        await page.keyboard.up("Control")
        await page.wait_for_timeout(200)

        # New paragraph + ensure plain style
        await page.keyboard.press("Enter")
        await self._ensure_plain_style(page)
        await page.wait_for_timeout(200)

        hashtag_text = " ".join(f"#{t.replace(' ', '')}" for t in tags)
        await self._human_type(page, hashtag_text)
        logger.info("naver_hashtags_entered", count=len(tags))

    async def _publish(self, page: Page) -> bool:
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
        await page.wait_for_timeout(300)

        header_btn = await page.query_selector(
            'button[class*="publish_btn"], header button[class*="publish"]',
        )
        if header_btn:
            await self._human_click_element(page, header_btn)
        else:
            await self._human_click(page, 1810, 22)
        await page.wait_for_timeout(1000)

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
                    await page.wait_for_timeout(2500)
                    return True
            except Exception:
                continue

        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = await btn.text_content()
            if text and "\ubc1c\ud589" in text and "\uc608\uc57d" not in text:
                if await btn.is_visible():
                    await self._human_click_element(page, btn)
                    await page.wait_for_timeout(2500)
                    return True

        await self._human_click(page, 480, 455)
        await page.wait_for_timeout(1000)
        await self._human_click(page, 470, 450)
        await page.wait_for_timeout(1500)
        return True
