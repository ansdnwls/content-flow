"""Naver SmartStore (Commerce API) adapter for product management."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult
from app.config import get_settings

_BASE_URL = "https://api.commerce.naver.com/external"

# Category cache TTL (seconds) — categories rarely change
_CATEGORY_CACHE_TTL = 3600


class NaverCommerceError(Exception):
    """Error from Naver Commerce API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        body: dict | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.body = body
        super().__init__(message)


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


def _build_headers(access_token: str) -> dict[str, str]:
    """Build request headers with Bearer token and HMAC signature."""
    settings = get_settings()
    ts = int(time.time() * 1000)
    client_id = settings.naver_commerce_client_id or ""
    client_secret = settings.naver_commerce_client_secret or ""
    sig = _sign_request(client_id, client_secret, ts)
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Naver-Client-Id": client_id,
        "X-Naver-Timestamp": str(ts),
        "X-Naver-Signature": sig,
    }


def _parse_error(resp: httpx.Response) -> NaverCommerceError:
    """Parse an error response into a NaverCommerceError."""
    try:
        body = resp.json()
    except Exception:
        body = {}
    message = body.get("message", body.get("detail", f"HTTP {resp.status_code}"))
    return NaverCommerceError(
        message=message,
        status_code=resp.status_code,
        error_code=body.get("code"),
        body=body,
    )


def _validate_image_url(url: str) -> bool:
    """Check that an image URL is a valid HTTPS URL with an image extension."""
    if not url.startswith("https://"):
        return False
    lower = url.lower()
    return any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"))


# ---------------------------------------------------------------------------
# Category cache
# ---------------------------------------------------------------------------

_category_cache: dict[str, Any] | None = None
_category_cache_ts: float = 0.0


async def get_categories(
    access_token: str,
    *,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch the full category tree from Naver Commerce API (cached).

    Returns a list of category dicts with id, name, and children.
    """
    global _category_cache, _category_cache_ts  # noqa: PLW0603

    now = time.time()
    if (
        not force_refresh
        and _category_cache is not None
        and (now - _category_cache_ts) < _CATEGORY_CACHE_TTL
    ):
        return _category_cache

    headers = _build_headers(access_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/v1/categories",
            headers=headers,
        )
        if resp.status_code != 200:
            raise _parse_error(resp)
        data = resp.json()

    categories = data if isinstance(data, list) else data.get("categories", [])
    _category_cache = categories
    _category_cache_ts = now
    return categories


def clear_category_cache() -> None:
    """Clear the in-memory category cache."""
    global _category_cache, _category_cache_ts  # noqa: PLW0603
    _category_cache = None
    _category_cache_ts = 0.0


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


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
        """Register a product on Naver SmartStore.

        Required credentials:
            access_token

        Required options:
            product_name, price, stock_quantity, category_id, detail_content (HTML)
        """
        access_token = credentials.get("access_token", "")
        if not access_token:
            return PublishResult(success=False, error="Missing access_token")

        product_name = options.get("product_name", "")
        if not product_name:
            return PublishResult(success=False, error="Missing product_name")

        price = options.get("price", 0)
        stock = options.get("stock_quantity", 0)
        category_id = options.get("category_id", "")
        detail_content = options.get("detail_content", text or "")

        image_urls = [m.url for m in media if m.media_type == "image"]

        # Validate image URLs
        for url in image_urls:
            if not _validate_image_url(url):
                return PublishResult(
                    success=False,
                    error=f"Invalid image URL: {url} (must be HTTPS with image extension)",
                )

        representative_image = {"url": image_urls[0]} if image_urls else {}
        optional_images = [{"url": url} for url in image_urls[1:9]]

        product_payload: dict[str, Any] = {
            "originProduct": {
                "statusType": "SALE",
                "saleType": "NEW",
                "leafCategoryId": category_id,
                "name": product_name,
                "detailContent": detail_content,
                "images": {
                    "representativeImage": representative_image,
                    "optionalImages": optional_images,
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

        headers = _build_headers(access_token)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE_URL}/v2/products",
                    headers=headers,
                    json=product_payload,
                )
                if resp.status_code == 429:
                    raise NaverCommerceError(
                        "Rate limit exceeded",
                        status_code=429,
                        error_code="RATE_LIMIT",
                    )
                if resp.status_code >= 400:
                    raise _parse_error(resp)
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
        except NaverCommerceError as exc:
            return PublishResult(
                success=False,
                error=f"Naver Commerce: {exc.message}",
                raw_response=exc.body,
            )
        except httpx.RequestError as exc:
            return PublishResult(
                success=False,
                error=f"Naver API request failed: {exc}",
            )

    async def get_product(
        self,
        product_id: str,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Fetch a single product by channel product number."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            raise NaverCommerceError("Missing access_token", status_code=401)

        headers = _build_headers(access_token)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_BASE_URL}/v2/products/channel-products/{product_id}",
                headers=headers,
            )
            if resp.status_code >= 400:
                raise _parse_error(resp)
            return resp.json()

    async def update_price(
        self,
        product_id: str,
        price: int,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Update the sale price of a product."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            raise NaverCommerceError("Missing access_token", status_code=401)

        headers = _build_headers(access_token)
        payload = {
            "originProduct": {
                "salePrice": price,
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{_BASE_URL}/v2/products/channel-products/{product_id}",
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                raise _parse_error(resp)
            return resp.json()

    async def update_stock(
        self,
        product_id: str,
        stock_quantity: int,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Update the stock quantity of a product."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            raise NaverCommerceError("Missing access_token", status_code=401)

        headers = _build_headers(access_token)
        payload = {
            "originProduct": {
                "stockQuantity": stock_quantity,
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{_BASE_URL}/v2/products/channel-products/{product_id}",
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                raise _parse_error(resp)
            return resp.json()

    async def delete(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
    ) -> bool:
        """Delete (delist) a product from SmartStore by setting status to SUSPENSION."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            return False

        headers = _build_headers(access_token)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    f"{_BASE_URL}/v2/products/channel-products/{platform_post_id}",
                    headers=headers,
                    json={"statusType": "SUSPENSION"},
                )
                if resp.status_code >= 400:
                    raise _parse_error(resp)
            return True
        except (NaverCommerceError, httpx.HTTPError):
            return False

    async def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> bool:
        """Validate Naver Commerce API credentials."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            return False

        headers = _build_headers(access_token)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}/v1/seller/shop",
                    headers=headers,
                )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_categories(
        self,
        credentials: dict[str, str],
        *,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch the category tree (delegates to module-level cached function)."""
        access_token = credentials.get("access_token", "")
        if not access_token:
            raise NaverCommerceError("Missing access_token", status_code=401)
        return await get_categories(access_token, force_refresh=force_refresh)
