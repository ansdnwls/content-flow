"""Content transformation service for platform-specific content bombs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from textwrap import shorten

import httpx

from app.config import get_settings


@dataclass(frozen=True, slots=True)
class PlatformRule:
    platform: str
    format: str
    audience_goal: str
    length_hint: str
    tone: str


PLATFORM_RULES: tuple[PlatformRule, ...] = (
    PlatformRule(
        "youtube",
        "long-form video brief",
        "deep educational watch time",
        "8-12 minutes",
        "authoritative",
    ),
    PlatformRule(
        "tiktok",
        "60-second short script",
        "high-retention hook",
        "under 60 seconds",
        "punchy",
    ),
    PlatformRule(
        "instagram",
        "60-second reels script",
        "visual storytelling",
        "under 60 seconds",
        "energetic",
    ),
    PlatformRule(
        "x",
        "text plus thumbnail concept",
        "280-char summary",
        "under 280 chars",
        "sharp",
    ),
    PlatformRule(
        "linkedin",
        "expert text plus video angle",
        "professional authority",
        "under 600 chars",
        "expert",
    ),
    PlatformRule(
        "blog",
        "full article with SEO tags",
        "search traffic",
        "1000+ words",
        "editorial",
    ),
    PlatformRule(
        "threads",
        "casual thread starter",
        "conversation",
        "under 500 chars",
        "casual",
    ),
    PlatformRule(
        "pinterest",
        "vertical pin concept",
        "click-through",
        "pin title + description",
        "inspirational",
    ),
    PlatformRule(
        "telegram",
        "markdown post with media",
        "community distribution",
        "concise post",
        "direct",
    ),
)


class ContentTransformer:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def transform_topic(self, topic: str) -> dict[str, dict]:
        """Generate platform-specific content variants for a topic."""
        if self.settings.anthropic_api_key:
            try:
                transformed = await self._transform_with_claude(topic)
                if transformed:
                    return transformed
            except httpx.HTTPError:
                pass

        return self._fallback_transform(topic)

    async def _transform_with_claude(self, topic: str) -> dict[str, dict]:
        prompt = self._build_prompt(topic)
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{self.settings.anthropic_api_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.settings.anthropic_model,
                    "max_tokens": 1800,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            text_parts = [
                part["text"]
                for part in payload.get("content", [])
                if part.get("type") == "text"
            ]
            if not text_parts:
                return {}
            return json.loads("".join(text_parts))

    @staticmethod
    def _build_prompt(topic: str) -> str:
        rules = "\n".join(
            (
                f"- {rule.platform}: format={rule.format}; "
                f"goal={rule.audience_goal}; "
                f"length={rule.length_hint}; "
                f"tone={rule.tone}"
            )
            for rule in PLATFORM_RULES
        )
        return (
            "Generate JSON keyed by platform for this topic.\n"
            f"Topic: {topic}\n"
            "For each platform, return title, body, media_prompt, "
            "seo_tags (array), publish_status='draft'.\n"
            "Follow these platform rules exactly:\n"
            f"{rules}\n"
            "Return only JSON."
        )

    @staticmethod
    def _fallback_transform(topic: str) -> dict[str, dict]:
        short_topic = shorten(topic, width=70, placeholder="...")
        return {
            "youtube": {
                "title": f"{short_topic} | Full breakdown",
                "body": (
                    f"Long-form video outline for {topic}. "
                    "Intro hook, 3 main sections, case study, and CTA. "
                    "Use yt-factory to expand into an 8-12 min brief."
                ),
                "media_prompt": f"Cinematic YouTube explainer visuals about {topic}",
                "seo_tags": [topic, "youtube", "explainer", "contentflow"],
                "publish_status": "draft",
            },
            "tiktok": {
                "title": f"{short_topic} in 60 seconds",
                "body": (
                    "Hook in 3 seconds, cut-driven short script explaining "
                    f"{topic} in under 60 seconds."
                ),
                "media_prompt": f"Fast-cut vertical short visuals about {topic}",
                "seo_tags": [topic, "tiktok", "shorts"],
                "publish_status": "draft",
            },
            "instagram": {
                "title": f"{short_topic} reel",
                "body": (
                    f"Reels-style short script for {topic} "
                    "with captions, visual beats, and CTA."
                ),
                "media_prompt": f"Instagram reels storyboard for {topic}",
                "seo_tags": [topic, "instagram", "reels"],
                "publish_status": "draft",
            },
            "x": {
                "title": short_topic,
                "body": shorten(
                    f"{topic}: sharp 280-char summary with "
                    "one insight, one proof point, and one CTA.",
                    width=280,
                    placeholder="...",
                ),
                "media_prompt": f"Thumbnail image concept summarizing {topic}",
                "seo_tags": [topic, "x", "summary"],
                "publish_status": "draft",
            },
            "linkedin": {
                "title": f"{short_topic} for operators",
                "body": shorten(
                    (
                        "Professional 600-character LinkedIn post on "
                        f"{topic} with a strategic takeaway and strong close."
                    ),
                    width=600,
                    placeholder="...",
                ),
                "media_prompt": (
                    f"Professional thought-leadership video thumbnail for {topic}"
                ),
                "seo_tags": [topic, "linkedin", "professional"],
                "publish_status": "draft",
            },
            "blog": {
                "title": f"{short_topic}: complete guide",
                "body": (
                    f"Blog structure for {topic}: intro, problem framing, "
                    "main body, video embed slot, conclusion, and SEO FAQ."
                ),
                "media_prompt": f"Featured blog hero image for {topic}",
                "seo_tags": [topic, "blog", "seo", "guide"],
                "publish_status": "draft",
            },
            "threads": {
                "title": f"{short_topic} thread",
                "body": shorten(
                    (
                        f"Casual Threads-style take on {topic} with a "
                        "relatable hook and conversational ending."
                    ),
                    width=500,
                    placeholder="...",
                ),
                "media_prompt": f"Casual mobile-first social visual for {topic}",
                "seo_tags": [topic, "threads"],
                "publish_status": "draft",
            },
            "pinterest": {
                "title": f"{short_topic} pin",
                "body": (
                    "Vertical image description and pin copy designed to "
                    f"drive clicks for {topic}."
                ),
                "media_prompt": f"Vertical Pinterest pin design for {topic}",
                "seo_tags": [topic, "pinterest", "pin"],
                "publish_status": "draft",
            },
            "telegram": {
                "title": f"{short_topic} update",
                "body": (
                    f"**{topic}**\n\nMarkdown-ready Telegram post with "
                    "concise summary and attached media note."
                ),
                "media_prompt": f"Telegram media preview for {topic}",
                "seo_tags": [topic, "telegram"],
                "publish_status": "draft",
            },
        }
