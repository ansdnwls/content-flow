"""Kakao Channel notification message renderer."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.product_image_analyzer import ProductAnalysis


@dataclass(frozen=True)
class KakaoContent:
    """Rendered Kakao Channel notification message."""
    title: str
    message: str
    button_label: str
    button_url: str
    image_url: str


def render_kakao(
    analysis: ProductAnalysis,
    price: int,
    images: list[str],
    product_url: str = "",
) -> KakaoContent:
    """
    Render Kakao Channel notification message.

    Args:
        analysis: Product analysis from image analyzer.
        price: Product price in KRW.
        images: Product image URLs.
        product_url: Link to the product page.
    """
    title = f"신상품 알림 | {analysis.product_name}"

    message_lines = [
        f"🆕 {analysis.product_name}",
        "",
        analysis.description_summary,
        "",
        f"💰 {price:,}원",
        "",
        *[f"✅ {sp}" for sp in analysis.selling_points[:3]],
    ]

    return KakaoContent(
        title=title,
        message="\n".join(message_lines),
        button_label="상품 보러가기",
        button_url=product_url,
        image_url=images[0] if images else "",
    )
