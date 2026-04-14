"""Multi-source content fetcher for card news generation.

Supported sources:
- youtube: Transcript extraction via youtube_transcript.py
- news: Google News RSS keyword search
- rss: Generic RSS/Atom feed parsing
- github: GitHub release notes
- url: Web page scraping
- text: Direct text input
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logging_config import get_logger
from app.services.youtube_transcript import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
)

logger = get_logger(__name__)

_VALID_SOURCE_TYPES = {"youtube", "news", "rss", "github", "url", "text"}


@dataclass
class ContentResult:
    """Unified content result from any source."""

    title: str
    text: str
    source_type: str  # youtube/news/rss/github/url/text
    source_url: str | None = None
    source_id: str = ""  # unique identifier (video_id, repo, keyword, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentFetcher:
    """Fetch content from various sources for card news generation."""

    async def fetch(
        self,
        source_type: str,
        source: str,
        **kwargs: Any,
    ) -> ContentResult:
        """Dispatch to the appropriate fetcher based on source_type."""
        if source_type not in _VALID_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type '{source_type}'. "
                f"Valid: {', '.join(sorted(_VALID_SOURCE_TYPES))}"
            )

        handler = getattr(self, f"fetch_{source_type}")
        return await handler(source, **kwargs)

    async def fetch_youtube(self, url: str, **_: Any) -> ContentResult:
        """Extract transcript from a YouTube video."""
        try:
            video_id = extract_video_id(url)
        except TranscriptError as exc:
            raise ValueError(f"Invalid YouTube URL: {exc}") from exc

        try:
            segments = fetch_transcript(video_id)
        except TranscriptError as exc:
            raise ValueError(f"Transcript fetch failed: {exc}") from exc

        raw_text = " ".join(seg["text"] for seg in segments)
        truncated = raw_text[:3000]
        if len(raw_text) > 3000:
            truncated += "...(이하 생략)"

        return ContentResult(
            title=f"YouTube: {video_id}",
            text=truncated,
            source_type="youtube",
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            source_id=video_id,
            metadata={"segment_count": len(segments)},
        )

    async def fetch_news(
        self, keyword: str, *, count: int = 5, **_: Any,
    ) -> ContentResult:
        """Fetch news articles via Google News RSS."""
        import feedparser

        from urllib.parse import quote

        rss_url = (
            f"https://news.google.com/rss/search?"
            f"q={quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
        )

        feed = await _fetch_feed(rss_url)
        if not feed.entries:
            raise ValueError(f"No news found for keyword: {keyword}")

        articles: list[str] = []
        for entry in feed.entries[:count]:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            # Strip HTML tags from summary
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            articles.append(f"[{title}] {clean_summary}")

        combined = "\n\n".join(articles)
        truncated = combined[:3000]
        if len(combined) > 3000:
            truncated += "...(이하 생략)"

        first_title = feed.entries[0].title if feed.entries else keyword
        logger.info("content_news_fetched", keyword=keyword, count=len(articles))

        return ContentResult(
            title=first_title,
            text=truncated,
            source_type="news",
            source_url=rss_url,
            source_id=keyword,
            metadata={"article_count": len(articles)},
        )

    async def fetch_rss(self, rss_url: str, **_: Any) -> ContentResult:
        """Parse a generic RSS/Atom feed."""
        feed = await _fetch_feed(rss_url)
        if not feed.entries:
            raise ValueError(f"Empty RSS feed: {rss_url}")

        articles: list[str] = []
        for entry in feed.entries[:5]:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            articles.append(f"[{title}] {clean_summary}")

        combined = "\n\n".join(articles)
        truncated = combined[:3000]
        if len(combined) > 3000:
            truncated += "...(이하 생략)"

        feed_title = getattr(feed.feed, "title", rss_url)
        logger.info("content_rss_fetched", url=rss_url, count=len(articles))

        return ContentResult(
            title=feed_title,
            text=truncated,
            source_type="rss",
            source_url=rss_url,
            source_id=rss_url,
            metadata={"article_count": len(articles)},
        )

    async def fetch_github(self, repo: str, **_: Any) -> ContentResult:
        """Fetch latest release notes from a GitHub repo."""
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 404:
                raise ValueError(f"No releases found for repo: {repo}")
            resp.raise_for_status()
            data = resp.json()

        tag = data.get("tag_name", "")
        name = data.get("name", tag)
        body = data.get("body", "")

        truncated = body[:3000]
        if len(body) > 3000:
            truncated += "...(이하 생략)"

        logger.info("content_github_fetched", repo=repo, tag=tag)

        return ContentResult(
            title=f"{repo} {name}",
            text=truncated,
            source_type="github",
            source_url=data.get("html_url"),
            source_id=repo,
            metadata={"tag": tag, "published_at": data.get("published_at")},
        )

    async def fetch_url(self, url: str, **_: Any) -> ContentResult:
        """Scrape a web page and extract main text content."""
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Extract main text from article or body
        article = soup.find("article") or soup.find("main") or soup.body
        text = article.get_text(separator="\n", strip=True) if article else ""

        truncated = text[:3000]
        if len(text) > 3000:
            truncated += "...(이하 생략)"

        logger.info("content_url_fetched", url=url, chars=len(truncated))

        return ContentResult(
            title=title or url,
            text=truncated,
            source_type="url",
            source_url=url,
            source_id=url,
        )

    async def fetch_text(
        self, text: str, *, title: str = "", **_: Any,
    ) -> ContentResult:
        """Accept direct text input."""
        if not text.strip():
            raise ValueError("Empty text provided")

        truncated = text[:3000]
        if len(text) > 3000:
            truncated += "...(이하 생략)"

        return ContentResult(
            title=title or truncated[:30] + "...",
            text=truncated,
            source_type="text",
            source_id="direct_input",
        )


async def _fetch_feed(url: str) -> Any:
    """Fetch and parse an RSS/Atom feed."""
    import feedparser

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    return feedparser.parse(resp.text)
