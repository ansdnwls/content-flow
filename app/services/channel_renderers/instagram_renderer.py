"""Instagram carousel content renderer."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.product_image_analyzer import ProductAnalysis


@dataclass(frozen=True)
class InstagramSlide:
    """Single slide in an Instagram carousel."""
    image_url: str
    overlay_text: str


@dataclass(frozen=True)
class InstagramContent:
    """Rendered Instagram carousel post."""
    slides: list[InstagramSlide] = field(default_factory=list)
    caption: str = ""
    hashtags: str = ""


def render_instagram(
    analysis: ProductAnalysis,
    price: int,
    images: list[str],
) -> InstagramContent:
    """
    Render Instagram carousel content.

    Args:
        analysis: Product analysis from image analyzer.
        price: Product price in KRW.
        images: Product image URLs.
    """
    slides: list[InstagramSlide] = []

    if images:
        slides.append(InstagramSlide(
            image_url=images[0],
            overlay_text=analysis.product_name,
        ))

    for i, point in enumerate(analysis.selling_points[:4]):
        img_url = images[min(i + 1, len(images) - 1)] if images else ""
        slides.append(InstagramSlide(
            image_url=img_url,
            overlay_text=point,
        ))

    if images:
        slides.append(InstagramSlide(
            image_url=images[-1],
            overlay_text=f"{price:,}원 | 지금 바로 만나보세요",
        ))

    caption_parts = [
        analysis.description_summary,
        "",
        *[f"✓ {sp}" for sp in analysis.selling_points],
        "",
        f"💰 {price:,}원",
        "",
        f"👤 {analysis.target_audience}",
    ]

    hashtags = " ".join(analysis.suggested_hashtags[:15])

    return InstagramContent(
        slides=slides,
        caption="\n".join(caption_parts),
        hashtags=hashtags,
    )
