"""Naver SmartStore product detail page HTML renderer."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.product_image_analyzer import ProductAnalysis


@dataclass(frozen=True)
class SmartStoreContent:
    """Rendered SmartStore product detail content."""
    html: str
    seo_title: str
    seo_description: str
    keywords: list[str] = field(default_factory=list)


def render_smart_store(
    analysis: ProductAnalysis,
    price: int,
    images: list[str],
) -> SmartStoreContent:
    """
    Render Naver SmartStore product detail page HTML.

    Args:
        analysis: Product analysis from image analyzer.
        price: Product price in KRW.
        images: Product image URLs.
    """
    selling_html = "".join(
        f"<li>{point}</li>" for point in analysis.selling_points
    )
    use_case_html = "".join(
        f"<li>{uc}</li>" for uc in analysis.use_cases
    )
    images_html = "".join(
        (
            f'<div class="product-image"><img src="{url}" '
            f'alt="{analysis.product_name}" loading="lazy" /></div>'
        )
        for url in images
    )
    price_formatted = f"{price:,}"

    html = (
        f'<div class="cf-product-detail">'
        f'<div class="cf-product-images">{images_html}</div>'
        f'<div class="cf-product-info">'
        f'<h1 class="cf-product-title">{analysis.product_name}</h1>'
        f'<p class="cf-product-price">{price_formatted}원</p>'
        f'<div class="cf-product-description">'
        f"<p>{analysis.description_summary}</p>"
        f"</div>"
        f'<div class="cf-product-features">'
        f"<h2>상품 특징</h2>"
        f"<ul>{selling_html}</ul>"
        f"</div>"
        f'<div class="cf-product-details">'
        f"<table>"
        f"<tr><th>색상</th><td>{analysis.main_color}</td></tr>"
        f"<tr><th>소재</th><td>{analysis.material}</td></tr>"
        f"<tr><th>스타일</th><td>{analysis.style}</td></tr>"
        f"</table>"
        f"</div>"
        f'<div class="cf-product-usecases">'
        f"<h2>이런 분께 추천해요</h2>"
        f"<p>{analysis.target_audience}</p>"
        f"<ul>{use_case_html}</ul>"
        f"</div>"
        f"</div>"
        f"</div>"
    )

    seo_title = f"{analysis.product_name} | {analysis.main_color} {analysis.style}"
    seo_desc = analysis.description_summary[:150]

    return SmartStoreContent(
        html=html,
        seo_title=seo_title,
        seo_description=seo_desc,
        keywords=list(analysis.suggested_keywords),
    )
