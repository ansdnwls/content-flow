"""Coupang WING Open API adapter — real API integration.

API docs: https://developers.coupangcorp.com/hc/en-us/articles/360033461914
Auth: HMAC-SHA256 signature with CEA authorization header.
Base URL: https://api-gateway.coupang.com
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

_BASE_URL = "https://api-gateway.coupang.com"
_PRODUCTS_PATH = (
    "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products"
)


class CoupangAPIError(Exception):
    """Raised when the Coupang WING API returns an error response."""

    def __init__(
        self, status_code: int, message: str, raw: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.raw = raw
        super().__init__(f"Coupang API {status_code}: {message}")


def _generate_signature(
    secret_key: str,
    method: str,
    path: str,
    query: str = "",
) -> tuple[str, str]:
    """Generate HMAC-SHA256 signature for Coupang WING API.

    Returns (authorization_header, datetime_str).
    """
    dt = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = dt + method.upper() + path + query
    signature = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature, dt


def _build_auth_header(
    access_key: str,
    secret_key: str,
    method: str,
    path: str,
    query: str = "",
) -> dict[str, str]:
    """Build the full Authorization and X-Requested-By headers."""
    signature, dt = _generate_signature(secret_key, method, path, query)
    authorization = (
        f"CEA algorithm=HmacSHA256, access-key={access_key}, "
        f"signed-date={dt}, signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8",
        "X-Requested-By": access_key,
    }


def _extract_error(resp: httpx.Response) -> str:
    """Extract error message from Coupang API response."""
    try:
        data = resp.json()
        return str(data.get("message", data.get("error", resp.text[:300])))
    except Exception:
        return resp.text[:300]


class CoupangWingAdapter(PlatformAdapter):
    """Coupang WING product registration adapter (live API)."""

    platform_name = "coupang_wing"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        """Register a product on Coupang.

        Required credentials:
            access_key, secret_key, vendor_id

        Required options:
            product_name, price, category_id

        Optional options:
            stock_quantity (default 99), detail_content (HTML),
            delivery_charge (default 0), brand, model_number
        """
        access_key = credentials.get("access_key", "")
        secret_key = credentials.get("secret_key", "")
        vendor_id = credentials.get("vendor_id", "")

        if not all([access_key, secret_key, vendor_id]):
            return PublishResult(
                success=False,
                error="Missing credentials: access_key, secret_key, vendor_id required",
            )

        product_name = options.get("product_name", "")
        if not product_name:
            return PublishResult(success=False, error="product_name is required")

        price = options.get("price", 0)
        category_id = options.get("category_id", "")
        if not category_id:
            return PublishResult(success=False, error="category_id is required")

        stock = options.get("stock_quantity", 99)
        detail_content = options.get("detail_content", text or "")
        delivery_charge = options.get("delivery_charge", 0)

        image_urls = [m.url for m in media if m.media_type == "image"]

        vendor_images = [
            {"vendorPath": url, "imageOrder": i}
            for i, url in enumerate(image_urls[:10])
        ]

        payload: dict[str, Any] = {
            "sellerProductName": product_name,
            "vendorId": vendor_id,
            "displayCategoryCode": int(category_id),
            "statusType": "SALE",
            "saleStartedAt": "",
            "saleEndedAt": "",
            "brand": options.get("brand", ""),
            "modelNumber": options.get("model_number", ""),
            "items": [
                {
                    "itemName": product_name,
                    "originalPrice": price,
                    "salePrice": price,
                    "maximumBuyCount": 999,
                    "maximumBuyForPerson": 0,
                    "outboundShippingTimeDay": 2,
                    "unitCount": 1,
                    "adultOnly": "EVERYONE",
                    "taxType": "TAX",
                    "parallelImported": "NOT_PARALLEL_IMPORTED",
                    "overseasPurchased": "NOT_OVERSEAS_PURCHASED",
                    "pccNeeded": False,
                    "images": vendor_images,
                    "notices": [],
                    "attributes": [],
                    "contents": [
                        {
                            "contentsType": "HTML",
                            "contentDetails": [
                                {"content": detail_content},
                            ],
                        },
                    ],
                    "offerCondition": "NEW",
                    "offerDescription": "",
                    "inventory": stock,
                },
            ],
            "deliveryInfo": {
                "deliveryType": "NORMAL",
                "deliveryAttributeType": "NORMAL",
                "deliveryCompanyCode": "KGB",
                "deliveryChargeType": (
                    "FREE" if delivery_charge == 0 else "PAID"
                ),
                "deliveryCharge": delivery_charge,
                "freeShipOverAmount": 0,
                "deliveryChargeOnReturn": 5000,
                "returnCenterCode": "",
                "outboundShippingPlaceCode": "",
            },
            "returnInfo": {
                "returnCharge": 5000,
                "returnChargeName": "반품배송비",
            },
        }

        path = _PRODUCTS_PATH
        headers = _build_auth_header(access_key, secret_key, "POST", path)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE_URL}{path}",
                    headers=headers,
                    json=payload,
                )

            if resp.status_code >= 400:
                error_msg = _extract_error(resp)
                return PublishResult(
                    success=False,
                    error=f"Coupang API {resp.status_code}: {error_msg}",
                    raw_response=resp.json() if resp.text else None,
                )

            data = resp.json()
            product_id = str(
                data.get("data", data.get("sellerProductId", ""))
            )

            return PublishResult(
                success=True,
                platform_post_id=product_id,
                url=f"https://www.coupang.com/vp/products/{product_id}",
                raw_response=data,
            )
        except httpx.RequestError as exc:
            return PublishResult(
                success=False,
                error=f"Coupang API request failed: {exc}",
            )

    async def get_product(
        self,
        seller_product_id: str,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Retrieve product details by seller product ID.

        Raises CoupangAPIError on failure.
        """
        access_key = credentials["access_key"]
        secret_key = credentials["secret_key"]

        path = f"{_PRODUCTS_PATH}/{seller_product_id}"
        headers = _build_auth_header(access_key, secret_key, "GET", path)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_BASE_URL}{path}", headers=headers,
            )

        if resp.status_code >= 400:
            raise CoupangAPIError(
                resp.status_code, _extract_error(resp),
                raw=resp.json() if resp.text else None,
            )
        return resp.json()

    async def update_price(
        self,
        seller_product_id: str,
        item_id: str,
        new_price: int,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Update the price of a product item.

        Raises CoupangAPIError on failure.
        """
        access_key = credentials["access_key"]
        secret_key = credentials["secret_key"]

        path = f"{_PRODUCTS_PATH}/{seller_product_id}/items/{item_id}"
        headers = _build_auth_header(access_key, secret_key, "PUT", path)

        payload = {
            "originalPrice": new_price,
            "salePrice": new_price,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{_BASE_URL}{path}", headers=headers, json=payload,
            )

        if resp.status_code >= 400:
            raise CoupangAPIError(
                resp.status_code, _extract_error(resp),
                raw=resp.json() if resp.text else None,
            )
        return resp.json()

    async def delete(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
    ) -> bool:
        """Delete (stop selling) a product on Coupang."""
        access_key = credentials.get("access_key", "")
        secret_key = credentials.get("secret_key", "")
        if not access_key or not secret_key:
            return False

        path = f"{_PRODUCTS_PATH}/{platform_post_id}"
        headers = _build_auth_header(access_key, secret_key, "DELETE", path)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.delete(
                    f"{_BASE_URL}{path}", headers=headers,
                )
            return resp.status_code < 400
        except httpx.HTTPError:
            return False

    async def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> bool:
        """Validate Coupang WING API credentials by calling a read endpoint."""
        access_key = credentials.get("access_key", "")
        secret_key = credentials.get("secret_key", "")
        vendor_id = credentials.get("vendor_id", "")
        if not all([access_key, secret_key, vendor_id]):
            return False

        path = (
            "/v2/providers/seller_api/apis/api/v1/marketplace"
            f"/seller-products/vendorId/{vendor_id}"
        )
        headers = _build_auth_header(access_key, secret_key, "GET", path)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}{path}", headers=headers,
                )
            return resp.status_code < 400
        except httpx.HTTPError:
            return False
