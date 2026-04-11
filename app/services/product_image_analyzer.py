"""Product image analysis using Claude Vision API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class ProductAnalysis:
    """Structured result from analyzing product images."""
    product_name: str
    main_color: str
    material: str
    style: str
    target_audience: str
    use_cases: list[str] = field(default_factory=list)
    selling_points: list[str] = field(default_factory=list)
    suggested_keywords: list[str] = field(default_factory=list)
    suggested_hashtags: list[str] = field(default_factory=list)
    description_summary: str = ""
    raw: dict[str, Any] | None = None


async def analyze_product(
    images: list[bytes],
    product_name: str = "",
    category: str = "",
) -> ProductAnalysis:
    """
    Analyze product images via Claude Vision API.

    Args:
        images: Raw image bytes (JPEG/PNG).
        product_name: Optional product name hint.
        category: Optional product category hint.

    Returns:
        Structured ProductAnalysis with extracted attributes.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    import base64
    content: list[dict[str, Any]] = []
    for img in images:
        encoded = base64.b64encode(img).decode()
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": encoded,
            },
        })

    hint_parts: list[str] = []
    if product_name:
        hint_parts.append(f"상품명: {product_name}")
    if category:
        hint_parts.append(f"카테고리: {category}")
    hint = "\n".join(hint_parts)

    prompt = (
        "당신은 한국 이커머스 상품 분석 전문가입니다.\n"
        "첨부된 상품 이미지를 분석하여 아래 JSON 형식으로 답변하세요.\n"
        f"{hint}\n\n"
        "반드시 아래 JSON만 출력하세요:\n"
        "{\n"
        '  "product_name": "상품명",\n'
        '  "main_color": "주요 색상",\n'
        '  "material": "소재/재질",\n'
        '  "style": "스타일 (캐주얼/포멀/스포티 등)",\n'
        '  "target_audience": "타겟 고객층",\n'
        '  "use_cases": ["용도1", "용도2"],\n'
        '  "selling_points": ["셀링포인트1", "셀링포인트2", "셀링포인트3"],\n'
        '  "suggested_keywords": ["키워드1", "키워드2"],\n'
        '  "suggested_hashtags": ["#해시태그1", "#해시태그2"],\n'
        '  "description_summary": "상품 설명 요약 (2-3문장)"\n'
        "}"
    )
    content.append({"type": "text", "text": prompt})

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.anthropic_api_base_url}/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": content}],
            },
        )
        resp.raise_for_status()

    from app.core.claude_utils import extract_claude_text, parse_claude_json

    data = resp.json()
    text = extract_claude_text(data)
    parsed = parse_claude_json(text)

    return ProductAnalysis(
        product_name=parsed.get("product_name", product_name),
        main_color=parsed.get("main_color", ""),
        material=parsed.get("material", ""),
        style=parsed.get("style", ""),
        target_audience=parsed.get("target_audience", ""),
        use_cases=parsed.get("use_cases", []),
        selling_points=parsed.get("selling_points", []),
        suggested_keywords=parsed.get("suggested_keywords", []),
        suggested_hashtags=parsed.get("suggested_hashtags", []),
        description_summary=parsed.get("description_summary", ""),
        raw=parsed,
    )
