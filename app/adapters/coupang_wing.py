"""Coupang WING Open API adapter (v1: mock implementation)."""
from __future__ import annotations

import uuid
from typing import Any

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult


class CoupangWingAdapter(PlatformAdapter):
    """
    Coupang WING product registration adapter.

    v1: Mock implementation. Coupang seller approval process is complex,
    so real API integration is deferred to v2.
    """

    platform_name = "coupang_wing"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        """
        Mock product registration on Coupang.

        Required options:
            product_name, price, category_id
        """
        product_name = options.get("product_name", "")
        if not product_name:
            return PublishResult(
                success=False,
                error="product_name is required",
            )

        mock_id = f"coupang_mock_{uuid.uuid4().hex[:12]}"

        return PublishResult(
            success=True,
            platform_post_id=mock_id,
            url=f"https://www.coupang.com/vp/products/{mock_id}",
            raw_response={
                "mock": True,
                "product_name": product_name,
                "price": options.get("price", 0),
                "category_id": options.get("category_id", ""),
                "note": "v1 mock - real API integration in v2",
            },
        )

    async def delete(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
    ) -> bool:
        """Mock product deletion."""
        return True

    async def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> bool:
        """Mock credential validation — always returns True in v1."""
        return True
