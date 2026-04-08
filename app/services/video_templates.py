"""Built-in video templates for AI generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SceneSpec:
    """A single scene in a video template."""

    name: str
    duration_seconds: int
    description: str
    caption_style: str = "bottom_center"


@dataclass(frozen=True)
class VideoTemplate:
    """Defines a reusable video generation template."""

    id: str
    name: str
    description: str
    duration_seconds: int
    scenes: tuple[SceneSpec, ...]
    caption_style: str = "bold_white"
    voice_tone: str = "neutral"
    bgm_mood: str = "ambient"
    is_builtin: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "duration_seconds": self.duration_seconds,
            "scenes": [
                {
                    "name": s.name,
                    "duration_seconds": s.duration_seconds,
                    "description": s.description,
                    "caption_style": s.caption_style,
                }
                for s in self.scenes
            ],
            "caption_style": self.caption_style,
            "voice_tone": self.voice_tone,
            "bgm_mood": self.bgm_mood,
            "is_builtin": self.is_builtin,
        }

    def to_yt_factory_params(self) -> dict[str, Any]:
        """Convert template into yt-factory pipeline parameters."""
        return {
            "template_id": self.id,
            "duration_seconds": self.duration_seconds,
            "scenes": [
                {
                    "name": s.name,
                    "duration": s.duration_seconds,
                    "caption_style": s.caption_style,
                }
                for s in self.scenes
            ],
            "caption_style": self.caption_style,
            "voice_tone": self.voice_tone,
            "bgm_mood": self.bgm_mood,
        }


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

NEWS_BRIEF = VideoTemplate(
    id="news_brief",
    name="News Brief",
    description="Fast-paced news summary with subtitle-driven visuals.",
    duration_seconds=30,
    caption_style="bold_white",
    voice_tone="authoritative",
    bgm_mood="urgent",
    scenes=(
        SceneSpec("hook", 5, "Attention-grabbing headline with bold text overlay."),
        SceneSpec("context", 10, "Background context with key facts on screen."),
        SceneSpec("detail", 10, "Core story details with supporting visuals."),
        SceneSpec("cta", 5, "Call-to-action: follow for more updates."),
    ),
)

QUOTE_CARD = VideoTemplate(
    id="quote_card",
    name="Quote Card",
    description="Typography-focused motivational or informational quote card.",
    duration_seconds=15,
    caption_style="centered_large",
    voice_tone="calm",
    bgm_mood="inspirational",
    scenes=(
        SceneSpec("intro", 3, "Fade-in with author or source attribution.", "top_center"),
        SceneSpec("quote", 9, "Full quote displayed with kinetic typography.", "centered_large"),
        SceneSpec("outro", 3, "Brand watermark and follow prompt.", "bottom_center"),
    ),
)

LISTICLE = VideoTemplate(
    id="listicle",
    name="Listicle",
    description="Countdown or ranked list format for TOP 5/10 content.",
    duration_seconds=60,
    caption_style="numbered_bold",
    voice_tone="energetic",
    bgm_mood="upbeat",
    scenes=(
        SceneSpec("intro", 8, "Topic introduction and list preview."),
        SceneSpec("items", 40, "Each list item with visual and quick explanation."),
        SceneSpec("recap", 7, "Quick recap of all items."),
        SceneSpec("cta", 5, "Engagement prompt: like, comment, subscribe."),
    ),
)

STORY = VideoTemplate(
    id="story",
    name="Story",
    description="Narrative-driven storytelling with emotional arc.",
    duration_seconds=90,
    caption_style="subtitle_bottom",
    voice_tone="conversational",
    bgm_mood="cinematic",
    scenes=(
        SceneSpec("hook", 10, "Emotional or surprising opening statement."),
        SceneSpec("setup", 20, "Establish characters, context, and stakes."),
        SceneSpec("conflict", 25, "Present the core problem or turning point."),
        SceneSpec("resolution", 25, "Show the outcome or lesson learned."),
        SceneSpec("cta", 10, "Closing message and engagement prompt."),
    ),
)

TUTORIAL = VideoTemplate(
    id="tutorial",
    name="Tutorial",
    description="Step-by-step instructional video with clear progression.",
    duration_seconds=120,
    caption_style="step_indicator",
    voice_tone="instructional",
    bgm_mood="focused",
    scenes=(
        SceneSpec("intro", 15, "What you will learn and prerequisites."),
        SceneSpec("step_1", 25, "First step with detailed visual walkthrough."),
        SceneSpec("step_2", 25, "Second step building on the first."),
        SceneSpec("step_3", 25, "Third step with tips and common mistakes."),
        SceneSpec("summary", 20, "Recap all steps with final result."),
        SceneSpec("cta", 10, "Resources link and subscribe prompt."),
    ),
)

BUILTIN_TEMPLATES: dict[str, VideoTemplate] = {
    t.id: t for t in [NEWS_BRIEF, QUOTE_CARD, LISTICLE, STORY, TUTORIAL]
}


def get_template(template_id: str) -> VideoTemplate | None:
    """Return a built-in template by ID, or None if not found."""
    return BUILTIN_TEMPLATES.get(template_id)


def list_builtin_templates() -> list[dict[str, Any]]:
    """Return all built-in templates as dicts."""
    return [t.to_dict() for t in BUILTIN_TEMPLATES.values()]


def db_row_to_template(row: dict) -> VideoTemplate:
    """Convert a database row into a VideoTemplate."""
    scenes = tuple(
        SceneSpec(
            name=s["name"],
            duration_seconds=s["duration_seconds"],
            description=s["description"],
            caption_style=s.get("caption_style", "bottom_center"),
        )
        for s in (row.get("scenes") or [])
    )
    return VideoTemplate(
        id=row["id"],
        name=row["name"],
        description=row.get("description", ""),
        duration_seconds=row.get("duration_seconds", 0),
        scenes=scenes,
        caption_style=row.get("caption_style", "bold_white"),
        voice_tone=row.get("voice_tone", "neutral"),
        bgm_mood=row.get("bgm_mood", "ambient"),
        is_builtin=False,
    )
