"""Viral Score prediction service — AI-powered content analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import get_settings

PLATFORM_OPTIMAL: dict[str, dict] = {
    "youtube": {
        "title_length": (40, 70),
        "description_length": (200, 5000),
        "tag_count": (5, 15),
        "tone": "authoritative, curiosity-driven",
    },
    "tiktok": {
        "title_length": (10, 50),
        "description_length": (20, 300),
        "tag_count": (3, 8),
        "tone": "punchy, trendy, hook-first",
    },
    "instagram": {
        "title_length": (10, 40),
        "description_length": (50, 2200),
        "tag_count": (5, 30),
        "tone": "energetic, visual, story-driven",
    },
    "x": {
        "title_length": (10, 50),
        "description_length": (10, 280),
        "tag_count": (1, 5),
        "tone": "sharp, witty, provocative",
    },
    "linkedin": {
        "title_length": (20, 60),
        "description_length": (100, 600),
        "tag_count": (3, 10),
        "tone": "professional, insightful",
    },
}


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    curiosity: int
    keyword_trend: int
    emotional_intensity: int
    platform_fit: int

    @property
    def total(self) -> int:
        return self.curiosity + self.keyword_trend + self.emotional_intensity + self.platform_fit


@dataclass(frozen=True, slots=True)
class ViralPrediction:
    viral_score: int
    breakdown: ScoreBreakdown
    suggestions: list[str]
    ab_variants: list[dict]


@dataclass(frozen=True, slots=True)
class ABTestResult:
    title_variants: list[str]
    description_variants: list[str]
    tag_variants: list[list[str]]


class ViralPredictor:
    """Predicts viral potential of content using Claude API."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def predict_viral_score(
        self,
        title: str,
        description: str,
        platform: str,
        tags: list[str] | None = None,
        thumbnail_url: str | None = None,
    ) -> ViralPrediction:
        """Predict viral score for content before publishing."""
        if self.settings.anthropic_api_key:
            try:
                result = await self._predict_with_claude(
                    title, description, platform, tags or [], thumbnail_url,
                )
                if result:
                    return result
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                pass

        return self._fallback_predict(title, description, platform, tags or [])

    async def generate_ab_test(
        self,
        title: str,
        description: str,
        platform: str,
        tags: list[str] | None = None,
    ) -> ABTestResult:
        """Generate A/B test variants for title, description, and tags."""
        if self.settings.anthropic_api_key:
            try:
                result = await self._ab_test_with_claude(
                    title, description, platform, tags or [],
                )
                if result:
                    return result
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                pass

        return self._fallback_ab_test(title, description, tags or [])

    async def _call_claude(self, prompt: str, max_tokens: int = 1200) -> dict:
        """Send a prompt to Claude API and return parsed JSON."""
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
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            from app.core.claude_utils import extract_claude_text, parse_claude_json

            text = extract_claude_text(payload)
            return parse_claude_json(text)

    async def _predict_with_claude(
        self,
        title: str,
        description: str,
        platform: str,
        tags: list[str],
        thumbnail_url: str | None,
    ) -> ViralPrediction:
        optimal = PLATFORM_OPTIMAL.get(platform, PLATFORM_OPTIMAL["youtube"])
        prompt = (
            "You are a viral content analyst. Evaluate this content and return JSON.\n\n"
            f"Platform: {platform}\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Tags: {', '.join(tags)}\n"
            f"Thumbnail URL: {thumbnail_url or 'none'}\n\n"
            f"Platform optimal settings:\n"
            f"- Title length: {optimal['title_length'][0]}-{optimal['title_length'][1]} chars\n"
            f"- Description length: "
            f"{optimal['description_length'][0]}-{optimal['description_length'][1]} chars\n"
            f"- Tag count: {optimal['tag_count'][0]}-{optimal['tag_count'][1]}\n"
            f"- Tone: {optimal['tone']}\n\n"
            "Score each dimension 0-25:\n"
            "1. curiosity: Does the title spark curiosity?\n"
            "2. keyword_trend: Do keywords match current trends?\n"
            "3. emotional_intensity: How emotionally engaging is the content?\n"
            "4. platform_fit: How well does it fit the platform format?\n\n"
            "Also provide:\n"
            "- suggestions: array of 3 actionable improvement tips\n"
            "- ab_variants: array of 3 alternative title+description combos\n\n"
            "Return ONLY JSON:\n"
            "{\n"
            '  "curiosity": <int>,\n'
            '  "keyword_trend": <int>,\n'
            '  "emotional_intensity": <int>,\n'
            '  "platform_fit": <int>,\n'
            '  "suggestions": ["tip1", "tip2", "tip3"],\n'
            '  "ab_variants": [\n'
            '    {"title": "...", "description": "..."},\n'
            '    {"title": "...", "description": "..."},\n'
            '    {"title": "...", "description": "..."}\n'
            "  ]\n"
            "}"
        )
        data = await self._call_claude(prompt)
        breakdown = ScoreBreakdown(
            curiosity=_clamp(data["curiosity"]),
            keyword_trend=_clamp(data["keyword_trend"]),
            emotional_intensity=_clamp(data["emotional_intensity"]),
            platform_fit=_clamp(data["platform_fit"]),
        )
        return ViralPrediction(
            viral_score=breakdown.total,
            breakdown=breakdown,
            suggestions=data.get("suggestions", [])[:3],
            ab_variants=data.get("ab_variants", [])[:3],
        )

    async def _ab_test_with_claude(
        self,
        title: str,
        description: str,
        platform: str,
        tags: list[str],
    ) -> ABTestResult:
        prompt = (
            "You are a social media A/B testing expert. Generate 3 variants each "
            "for title, description, and tags. Return JSON only.\n\n"
            f"Platform: {platform}\n"
            f"Original title: {title}\n"
            f"Original description: {description}\n"
            f"Original tags: {', '.join(tags)}\n\n"
            "Return ONLY JSON:\n"
            "{\n"
            '  "title_variants": ["v1", "v2", "v3"],\n'
            '  "description_variants": ["v1", "v2", "v3"],\n'
            '  "tag_variants": [["t1","t2"], ["t1","t2"], ["t1","t2"]]\n'
            "}"
        )
        data = await self._call_claude(prompt)
        return ABTestResult(
            title_variants=data["title_variants"][:3],
            description_variants=data["description_variants"][:3],
            tag_variants=data["tag_variants"][:3],
        )

    @staticmethod
    def _fallback_predict(
        title: str,
        description: str,
        platform: str,
        tags: list[str],
    ) -> ViralPrediction:
        """Heuristic-based fallback when Claude API is unavailable."""
        optimal = PLATFORM_OPTIMAL.get(platform, PLATFORM_OPTIMAL["youtube"])
        title_len = len(title)
        desc_len = len(description)
        tag_count = len(tags)

        # Curiosity: title length + question/number presence
        curiosity = 10
        t_min, t_max = optimal["title_length"]
        if t_min <= title_len <= t_max:
            curiosity += 5
        if any(c in title for c in "?!"):
            curiosity += 5
        if any(ch.isdigit() for ch in title):
            curiosity += 5

        # Keyword trend: tag count within optimal range
        keyword_trend = 10
        tg_min, tg_max = optimal["tag_count"]
        if tg_min <= tag_count <= tg_max:
            keyword_trend += 10
        elif tag_count > 0:
            keyword_trend += 5

        # Emotional intensity: exclamation, caps words, power words
        emotional = 10
        if "!" in title or "!" in description:
            emotional += 5
        power_words = {"secret", "shocking", "amazing", "ultimate", "proven", "free"}
        if any(w in title.lower() or w in description.lower() for w in power_words):
            emotional += 5
        if sum(1 for w in title.split() if w.isupper() and len(w) > 1) > 0:
            emotional += 5

        # Platform fit: description length
        platform_fit = 10
        d_min, d_max = optimal["description_length"]
        if d_min <= desc_len <= d_max:
            platform_fit += 10
        elif desc_len > 0:
            platform_fit += 5

        breakdown = ScoreBreakdown(
            curiosity=min(curiosity, 25),
            keyword_trend=min(keyword_trend, 25),
            emotional_intensity=min(emotional, 25),
            platform_fit=min(platform_fit, 25),
        )

        suggestions = _generate_suggestions(title, description, tags, optimal)

        return ViralPrediction(
            viral_score=breakdown.total,
            breakdown=breakdown,
            suggestions=suggestions[:3],
            ab_variants=[
                {"title": f"{title} — You Won't Believe This", "description": description},
                {"title": f"Why {title} Changes Everything", "description": description},
                {"title": f"The Truth About {title}", "description": description},
            ],
        )

    @staticmethod
    def _fallback_ab_test(
        title: str,
        description: str,
        tags: list[str],
    ) -> ABTestResult:
        """Heuristic A/B test variant generation."""
        return ABTestResult(
            title_variants=[
                f"{title} — The Complete Guide",
                f"Why {title} Matters More Than You Think",
                f"{title}: What Nobody Tells You",
            ],
            description_variants=[
                f"Discover the secrets behind {description[:80]}...",
                f"Everything you need to know: {description[:80]}...",
                f"The ultimate breakdown of {description[:80]}...",
            ],
            tag_variants=[
                [*tags[:3], "trending", "viral"],
                [*tags[:3], "mustwatch", "guide"],
                [*tags[:3], "howto", "tips"],
            ],
        )


def _clamp(value: int, lo: int = 0, hi: int = 25) -> int:
    """Clamp an integer to [lo, hi]."""
    return max(lo, min(hi, int(value)))


def _generate_suggestions(
    title: str,
    description: str,
    tags: list[str],
    optimal: dict,
) -> list[str]:
    """Generate heuristic improvement suggestions."""
    suggestions: list[str] = []
    t_min, t_max = optimal["title_length"]
    title_len = len(title)

    if title_len < t_min:
        suggestions.append(
            f"Title is too short ({title_len} chars). "
            f"Aim for {t_min}-{t_max} characters for better engagement."
        )
    elif title_len > t_max:
        suggestions.append(
            f"Title is too long ({title_len} chars). "
            f"Shorten to {t_min}-{t_max} characters for higher CTR."
        )

    if not any(c in title for c in "?!"):
        suggestions.append(
            "Add a question mark or exclamation to your title to spark curiosity."
        )

    tg_min, tg_max = optimal["tag_count"]
    tag_count = len(tags)
    if tag_count < tg_min:
        suggestions.append(
            f"Add more tags (currently {tag_count}, optimal {tg_min}-{tg_max})."
        )

    d_min, d_max = optimal["description_length"]
    desc_len = len(description)
    if desc_len < d_min:
        suggestions.append(
            f"Description is too short ({desc_len} chars). "
            f"Expand to at least {d_min} characters."
        )

    if not suggestions:
        suggestions.append("Content looks well-optimized! Consider A/B testing variants.")

    return suggestions[:3]
