"""Coupang product description renderer."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.product_image_analyzer import ProductAnalysis


@dataclass(frozen=True)
class CoupangContent:
    """Rendered Coupang product description."""
    title: str
    description: str
    bullet_points: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


def render_coupang(
    analysis: ProductAnalysis,
    price: int,
) -> CoupangContent:
    """
    Render Coupang product listing content.

    Args:
        analysis: Product analysis from image analyzer.
        price: Product price in KRW.
    """
    title = f"{analysis.product_name} {analysis.main_color} {analysis.style}"

    bullets = [
        f"소재: {analysis.material}",
        f"색상: {analysis.main_color}",
        f"스타일: {analysis.style}",
        *[f"포인트: {sp}" for sp in analysis.selling_points[:3]],
    ]

    desc_lines = [
        analysis.description_summary,
        "",
        "추천 대상",
        f"- {analysis.target_audience}",
        "",
        "활용",
        *[f"- {uc}" for uc in analysis.use_cases],
    ]

    return CoupangContent(
        title=title,
        description="\n".join(desc_lines),
        bullet_points=bullets,
        keywords=list(analysis.suggested_keywords),
    )
