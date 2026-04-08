"""Naver SmartStore (Commerce API) adapter for product management."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

_BASE_URL = "https://api.commerce.naver.com/external"


def _sign_request(
    client_id: str,
    client_secret: str,
    timestamp: int,
) -> str:
    """Generate HMAC-SHA256 signature for Naver Commerce API."""
    base = f"{client_id}_{timestamp}"
    return hmac.new(
        client_secret.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()


class NaverSmartStoreAdapter(PlatformAdapter):
    """Naver SmartStore product registration adapter."""

    platform_name = "naver_smart_store"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        """
        Register a product on Naver SmartStore.

        Required credentials:
            client_id, client_secret, access_token

        Required options:
            product_name, price, stock_quantity, category_id, detail_content (HTML)
        """
        access_token = credentials.get("access_token", "")
        if not access_token:
            return PublishResult(success=False, error="Missing access_token")

        product_name = options.get("product_name", "")
        price = options.get("price", 0)
        stock = options.get("stock_quantity", 0)
        category_id = options.get("category_id", "")
        detail_content = options.get("detail_content", text or "")

        image_urls = [m.url for m in media if m.media_type == "image"]

        product_payload: dict[str, Any] = {
            "originProduct": {
                "statusType": "SALE",
                "saleType": "NEW",
                "leafCategoryId": category_id,
                "name": product_name,
                "detailContent": detail_content,
                "images": {
                    "representativeImage": {"url": image_urls[0]} if image_urls else {},
                    "optionalImages": [
                        {"url": url} for url in image_urls[1:9]
                    ],
                },
                "salePrice": price,
                "stockQuantity": stock,
                "deliveryInfo": options.get("delivery_info", {
                    "deliveryType": "DELIVERY",
                    "deliveryAttributeType": "NORMAL",
                    "deliveryFee": {"deliveryFeeType": "FREE"},
                }),
            },
            "smartstoreChannelProduct": {
                "channelProductName": product_name,
                "naverShoppingRegistration": True,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE_URL}/v2/products",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=product_payload,
                )
                resp.raise_for_status()
                data = resp.json()

            product_id = str(data.get("smartstoreChannelProductNo", ""))
            url = (
                f"https://smartstore.naver.com/products/{product_id}"
                if product_id else None
            )

            return PublishResult(
                success=True,
                platform_post_id=product_id,
                url=url,
                raw_response=data,
            )
        except httpx.HTTPStatusError as exc:
            return PublishResult(
                success=False,
                error=f"Naver API error {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.RequestError as exc:
            return PublishResult(
                success=False,
                error=f"Naver API request failed: {exc}",
            )

    async def delete(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
    ) -> bool:
        """Delete (delist) a product from SmartStore."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            return False

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    f"{_BASE_URL}/v2/products/channel-products/{platform_post_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"statusType": "SUSPENSION"},
                )
                resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> bool:
        """Validate Naver Commerce API credentials."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}/v1/seller/shop",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
