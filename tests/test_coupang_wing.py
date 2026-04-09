"""Tests for Coupang WING Open API adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.adapters.base import MediaSpec
from app.adapters.coupang_wing import (
    CoupangAPIError,
    CoupangWingAdapter,
    _build_auth_header,
    _generate_signature,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter() -> CoupangWingAdapter:
    return CoupangWingAdapter()


@pytest.fixture()
def valid_credentials() -> dict[str, str]:
    return {
        "access_key": "test_access_key",
        "secret_key": "test_secret_key",
        "vendor_id": "test_vendor_123",
    }


@pytest.fixture()
def publish_options() -> dict:
    return {
        "product_name": "Test Product",
        "price": 15000,
        "category_id": "50000001",
        "stock_quantity": 100,
        "detail_content": "<h1>Great product</h1>",
    }


# ---------------------------------------------------------------------------
# 1. Signature generation
# ---------------------------------------------------------------------------


def test_generate_signature_returns_hex_and_datetime():
    """_generate_signature should return a hex signature and datetime string."""
    sig, dt = _generate_signature("secret", "GET", "/v2/test")
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex digest
    assert dt.endswith("Z")


def test_generate_signature_deterministic():
    """Same inputs at the same moment should produce the same signature."""
    with patch("app.adapters.coupang_wing.time") as mock_time:
        mock_time.strftime.return_value = "260409T120000Z"
        mock_time.gmtime.return_value = None
        sig1, _ = _generate_signature("secret", "GET", "/path")
        sig2, _ = _generate_signature("secret", "GET", "/path")
    assert sig1 == sig2


# ---------------------------------------------------------------------------
# 2. Auth header construction
# ---------------------------------------------------------------------------


def test_build_auth_header_contains_cea():
    """_build_auth_header should return CEA authorization header."""
    headers = _build_auth_header("ak", "sk", "GET", "/path")
    assert "CEA algorithm=HmacSHA256" in headers["Authorization"]
    assert "access-key=ak" in headers["Authorization"]
    assert headers["Content-Type"] == "application/json;charset=UTF-8"
    assert headers["X-Requested-By"] == "ak"


# ---------------------------------------------------------------------------
# 3. Publish success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_success(adapter, valid_credentials, publish_options):
    """publish should register a product and return success with product ID."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"data": "12345"}'
    mock_response.json.return_value = {"data": "12345"}

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(post=AsyncMock(return_value=mock_response)),
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[MediaSpec(url="https://cdn.example.com/img.jpg", media_type="image")],
            options=publish_options,
            credentials=valid_credentials,
        )

    assert result.success is True
    assert result.platform_post_id == "12345"
    assert "coupang.com" in (result.url or "")


# ---------------------------------------------------------------------------
# 4. Publish with missing credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_missing_credentials(adapter, publish_options):
    """publish should return failure when credentials are missing."""
    result = await adapter.publish(
        text=None,
        media=[],
        options=publish_options,
        credentials={"access_key": "ak"},  # missing secret_key, vendor_id
    )
    assert result.success is False
    assert "Missing credentials" in (result.error or "")


# ---------------------------------------------------------------------------
# 5. Publish with missing product_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_missing_product_name(adapter, valid_credentials):
    """publish should return failure when product_name is empty."""
    result = await adapter.publish(
        text=None,
        media=[],
        options={"price": 10000, "category_id": "50000001"},
        credentials=valid_credentials,
    )
    assert result.success is False
    assert "product_name" in (result.error or "")


# ---------------------------------------------------------------------------
# 6. Publish with missing category_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_missing_category_id(adapter, valid_credentials):
    """publish should return failure when category_id is empty."""
    result = await adapter.publish(
        text=None,
        media=[],
        options={"product_name": "Test", "price": 10000},
        credentials=valid_credentials,
    )
    assert result.success is False
    assert "category_id" in (result.error or "")


# ---------------------------------------------------------------------------
# 7. Publish API error (4xx)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_api_error(adapter, valid_credentials, publish_options):
    """publish should return failure on Coupang API 400+ response."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"message": "Bad request"}'
    mock_response.json.return_value = {"message": "Bad request"}

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(post=AsyncMock(return_value=mock_response)),
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[],
            options=publish_options,
            credentials=valid_credentials,
        )

    assert result.success is False
    assert "400" in (result.error or "")


# ---------------------------------------------------------------------------
# 8. Publish network error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_network_error(adapter, valid_credentials, publish_options):
    """publish should return failure on network error."""
    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                post=AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
            ),
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[],
            options=publish_options,
            credentials=valid_credentials,
        )

    assert result.success is False
    assert "request failed" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# 9. Get product success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_get_product_success(adapter, valid_credentials):
    """get_product should return product data on success."""
    product_data = {
        "sellerProductId": "12345",
        "sellerProductName": "Test Product",
        "statusType": "SALE",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = product_data

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.get_product("12345", valid_credentials)

    assert result["sellerProductName"] == "Test Product"


# ---------------------------------------------------------------------------
# 10. Get product raises CoupangAPIError on failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_get_product_api_error(adapter, valid_credentials):
    """get_product should raise CoupangAPIError on 4xx response."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"message": "Product not found"}'
    mock_response.json.return_value = {"message": "Product not found"}

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(CoupangAPIError) as exc_info:
            await adapter.get_product("99999", valid_credentials)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 11. Delete product
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_delete_product_success(adapter, valid_credentials):
    """delete should return True on successful deletion."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.delete = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.delete("12345", valid_credentials)

    assert result is True


# ---------------------------------------------------------------------------
# 12. Validate credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_validate_credentials_success(adapter, valid_credentials):
    """validate_credentials should return True on 200."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("app.adapters.coupang_wing.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.validate_credentials(valid_credentials)

    assert result is True


@pytest.mark.asyncio()
async def test_validate_credentials_missing():
    """validate_credentials should return False when keys are missing."""
    adapter = CoupangWingAdapter()
    result = await adapter.validate_credentials({"access_key": "ak"})
    assert result is False
