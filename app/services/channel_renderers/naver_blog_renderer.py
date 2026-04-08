"""Naver Blog / Tistory SEO-optimized blog post renderer."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.product_image_analyzer import ProductAnalysis


@dataclass(frozen=True)
class NaverBlogContent:
    """Rendered blog post content."""
    title: str
    body_html: str
    tags: list[str] = field(default_factory=list)
    meta_description: str = ""


def render_naver_blog(
    analysis: ProductAnalysis,
    price: int,
    images: list[str],
) -> NaverBlogContent:
    """
    Render SEO-optimized blog post for Naver Blog / Tistory.

    Args:
        analysis: Product analysis from image analyzer.
        price: Product price in KRW.
        images: Product image URLs.
    """
    title = f"{analysis.product_name} 리뷰 | {analysis.main_color} {analysis.style} 추천"

    sections: list[str] = []

    sections.append(f"<h2>{analysis.product_name} 소개</h2>")
    sections.append(f"<p>{analysis.description_summary}</p>")
    if images:
        sections.append(
            f'<figure><img src="{images[0]}" alt="{analysis.product_name}" />'
            f"<figcaption>{analysis.product_name}</figcaption></figure>"
        )

    sections.append("<h2>상품 특징</h2>")
    sections.append("<ul>")
    for sp in analysis.selling_points:
        sections.append(f"<li><strong>{sp}</strong></li>")
    sections.append("</ul>")

    if len(images) > 1:
        sections.append("<h2>상세 이미지</h2>")
        for img in images[1:4]:
            sections.append(
                f'<figure><img src="{img}" alt="{analysis.product_name}" /></figure>'
            )

    sections.append("<h2>상품 정보</h2>")
    sections.append(
        "<table>"
        f"<tr><th>색상</th><td>{analysis.main_color}</td></tr>"
        f"<tr><th>소재</th><td>{analysis.material}</td></tr>"
        f"<tr><th>스타일</th><td>{analysis.style}</td></tr>"
        f"<tr><th>가격</th><td>{price:,}원</td></tr>"
        "</table>"
    )

    sections.append("<h2>이런 분께 추천합니다</h2>")
    sections.append(f"<p>{analysis.target_audience}</p>")
    sections.append("<ul>")
    for uc in analysis.use_cases:
        sections.append(f"<li>{uc}</li>")
    sections.append("</ul>")

    sections.append("<h2>마무리</h2>")
    sections.append(
        f"<p>{analysis.product_name}, {analysis.main_color} 컬러의 "
        f"{analysis.style} 스타일로 {analysis.target_audience}에게 "
        f"추천드립니다. 지금 바로 확인해보세요!</p>"
    )

    body_html = "\n".join(sections)
    tags = list(analysis.suggested_keywords[:10])
    meta = analysis.description_summary[:160]

    return NaverBlogContent(
        title=title,
        body_html=body_html,
        tags=tags,
        meta_description=meta,
    )
