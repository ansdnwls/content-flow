"""Naver Blog posting via Playwright browser automation.

Uses playwright-stealth to bypass bot detection since
Naver Blog Write API has been officially deprecated.
"""
from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import async_playwright, BrowserContext, Page

from app.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Stealth browser helpers
# ---------------------------------------------------------------------------

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_ANTI_DETECT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
"""


def _random_delay(low: int = 3, high: int = 30) -> int:
    """Return a random typing delay in milliseconds."""
    return random.randint(low, high)


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
                viewport={"width": 1280, "height": 800},
                locale="ko-KR",
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

            # Poll for login completion (max 5 minutes)
            _LOGIN_PATHS = ("nidlogin", "/nidlogin.login")
            logged_in = False
            for tick in range(300):
                await page.wait_for_timeout(1000)
                try:
                    url = page.url
                    # Logged in = left the login page entirely
                    if "naver.com" in url and not any(p in url for p in _LOGIN_PATHS):
                        logged_in = True
                        break
                    # Also detect NID cookie as fallback
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

            # Navigate to blog to fully establish cookies
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
    # Posting
    # ------------------------------------------------------------------

    async def post(
        self,
        title: str,
        content: str,
        *,
        images: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write and publish a blog post.

        Args:
            title: Blog post title.
            content: Plain-text body. Sections separated by ``\\n\\n``.
            images: Optional list of image file paths or HTTP URLs.
            tags: Optional list of hashtag strings (without ``#``).

        Returns:
            Dict with ``success``, ``url``, and optional ``error``.
        """
        if not self.has_session():
            return {"success": False, "error": "No session file. Run setup_session() first."}
        if not self.blog_id:
            return {"success": False, "error": "NAVER_BLOG_ID not configured."}

        from playwright_stealth import Stealth

        # Resolve images: download URLs to temp files
        local_images: list[Path] = []
        temp_dir = None
        if images:
            temp_dir = tempfile.mkdtemp(prefix="naver_blog_")
            for i, img in enumerate(images):
                try:
                    resolved = await self._resolve_image(img, Path(temp_dir), i)
                    if resolved:
                        local_images.append(resolved)
                except Exception as exc:
                    logger.warning("image_resolve_failed", index=i, error=str(exc))

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=False,
                    slow_mo=80,
                    args=_BROWSER_ARGS,
                )
                context = await browser.new_context(
                    storage_state=str(self.session_path),
                    viewport={"width": 1280, "height": 900},
                    locale="ko-KR",
                    user_agent=_USER_AGENT,
                )
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                await page.add_init_script(_ANTI_DETECT_SCRIPT)

                # Step 1: Open editor
                await self._open_editor(page)

                # Step 2: Type title
                await self._input_title(page, title)

                # Step 3: Move to body area
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(500)

                # Step 4: Alternate image upload + text sections
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

                # Save updated session (cookies may have refreshed)
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
                        "warning": "Publish clicked but PostView URL not confirmed. Check manually.",
                    }

        except Exception as exc:
            logger.error("naver_blog_post_failed", error=str(exc))
            return {"success": False, "error": str(exc)}
        finally:
            # Clean up temp images
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internal helpers
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
                await cancel.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        logger.info("naver_editor_opened")

    async def _input_title(self, page: Page, title: str) -> None:
        """Click the title area and type."""
        title_el = await page.query_selector(
            ".se-documentTitle .se-text-paragraph"
        )
        if title_el:
            await title_el.click()
        else:
            await page.mouse.click(640, 130)
        await page.wait_for_timeout(300)
        await page.keyboard.type(title, delay=_random_delay(20, 40))
        logger.info("naver_title_entered", title=title[:50])

    async def _upload_one_image(self, page: Page, image_path: Path) -> bool:
        """Upload a single image via the editor toolbar button."""
        try:
            image_btn = await page.query_selector('button[data-name="image"]')
            if not image_btn:
                return False

            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await image_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))
            await page.wait_for_timeout(2500)
            return True
        except Exception as exc:
            logger.warning("naver_image_upload_failed", error=str(exc))
            return False

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
            # Upload image if available
            if i < len(images):
                if await self._upload_one_image(page, images[i]):
                    uploaded += 1

            # Type text section if available
            if i < len(sections):
                await self._type_section(page, sections[i])
                await page.wait_for_timeout(300)

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
                await page.keyboard.type(line, delay=_random_delay(3, 15))
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(50)
        # Extra spacing after section
        await page.keyboard.press("Enter")

    async def _input_hashtags(self, page: Page, tags: list[str]) -> None:
        """Type hashtags at the end of the post."""
        await page.keyboard.press("Enter")
        hashtag_text = " ".join(f"#{t.replace(' ', '')}" for t in tags)
        await page.keyboard.type(hashtag_text, delay=_random_delay(5, 15))
        logger.info("naver_hashtags_entered", count=len(tags))

    async def _publish(self, page: Page) -> bool:
        """Click publish buttons (header -> confirm dialog)."""
        # Close help panels / tooltips
        for _ in range(5):
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)

        close_selectors = [
            '.help_layer button[class*="close"]',
            '.tooltip button[class*="close"]',
            '.se-help-panel-close-button',
            'button[aria-label="닫기"]',
        ]
        for sel in close_selectors:
            btn = await page.query_selector(sel)
            if btn:
                try:
                    await btn.click()
                except Exception:
                    pass
                await page.wait_for_timeout(300)

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)

        # Click header publish button
        header_btn = await page.query_selector(
            'button[class*="publish_btn"], header button[class*="publish"]'
        )
        if header_btn:
            await header_btn.click(force=True)
        else:
            await page.mouse.click(1210, 22)
        await page.wait_for_timeout(2000)

        # Click final confirm button in publish dialog
        confirm_selectors = [
            'button.confirm_btn__WEaBq',
            'button[class*="confirm_btn"]',
            'button.btn_publish__FvD4K',
            'button[class*="btn_publish"]',
            '.publish_layer button[class*="confirm"]',
        ]
        for sel in confirm_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click(force=True)
                    await page.wait_for_timeout(5000)
                    return True
            except Exception:
                continue

        # Try finding button by text content
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = await btn.text_content()
            if text and "발행" in text and "예약" not in text:
                if await btn.is_visible():
                    await btn.click(force=True)
                    await page.wait_for_timeout(5000)
                    return True

        # Fallback: coordinate clicks
        await page.mouse.click(480, 455)
        await page.wait_for_timeout(2000)
        await page.mouse.click(470, 450)
        await page.wait_for_timeout(3000)
        return True
