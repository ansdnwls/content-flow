"""Tests for Naver Commerce (SmartStore) OAuth + product adapter."""
from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import MediaSpec
from app.adapters.naver_smart_store import (
    NaverSmartStoreAdapter,
    _validate_image_url,
    clear_category_cache,
    get_categories,
)
from app.oauth.providers.naver_commerce import (
    NaverCommerceOAuthProvider,
    generate_signature,
    verify_signature,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear category cache before each test."""
    clear_category_cache()
    yield
    clear_category_cache()


@pytest.fixture()
def _fake_settings(monkeypatch):
    """Patch get_settings to return fake Naver Commerce config."""
    fake = MagicMock()
    fake.naver_commerce_client_id = "test_client_id"
    fake.naver_commerce_client_secret = "test_client_secret"
    fake.naver_commerce_redirect_uri = "http://localhost:8000/api/v1/accounts/callback/naver_commerce"
    fake.oauth_redirect_base_url = "http://localhost:8000"
    monkeypatch.setattr(
        "app.oauth.providers.naver_commerce.get_settings", lambda: fake,
    )
    monkeypatch.setattr(
        "app.adapters.naver_smart_store.get_settings", lambda: fake,
    )
    return fake


@pytest.fixture()
def adapter():
    return NaverSmartStoreAdapter()


@pytest.fixture()
def provider():
    return NaverCommerceOAuthProvider()


@pytest.fixture()
def valid_credentials():
    return {"access_token": "test_access_token"}


# ---------------------------------------------------------------------------
# 1. OAuth flow: authorize → callback → token
# ---------------------------------------------------------------------------

def test_authorize_url_contains_required_params(_fake_settings, provider):
    """authorize_url should contain client_id, redirect_uri, state, scope."""
    url = provider.get_authorize_url(state="test_state_123")
    assert "client_id=test_client_id" in url
    assert "state=test_state_123" in url
    assert "response_type=code" in url
    assert "scope=" in url


@pytest.mark.asyncio()
async def test_exchange_code_returns_tokens(_fake_settings, provider):
    """exchange_code should POST to token URL and return OAuthTokenResponse."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "product",
    }

    with patch("app.oauth.providers.naver_commerce.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await provider.exchange_code("auth_code_123", "http://localhost/callback")

    assert result.access_token == "new_access_token"
    assert result.refresh_token == "new_refresh_token"
    assert result.expires_in == 3600


# ---------------------------------------------------------------------------
# 2. Product registration success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_publish_product_success(_fake_settings, adapter, valid_credentials):
    """publish should register a product and return success with product ID."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "smartstoreChannelProductNo": "12345",
        "originProductNo": "67890",
    }

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[MediaSpec(url="https://cdn.example.com/img.jpg", media_type="image")],
            options={
                "product_name": "Test Product",
                "price": 15000,
                "stock_quantity": 100,
                "category_id": "50000001",
                "detail_content": "<h1>Great product</h1>",
            },
            credentials=valid_credentials,
        )

    assert result.success is True
    assert result.platform_post_id == "12345"
    assert "smartstore.naver.com" in (result.url or "")


# ---------------------------------------------------------------------------
# 3. Token expiry → refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_refresh_token_success(_fake_settings, provider):
    """refresh_access_token should return new tokens."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "access_token": "refreshed_token",
        "refresh_token": "new_refresh",
        "expires_in": 7200,
    }

    with patch("app.oauth.providers.naver_commerce.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await provider.refresh_access_token("old_refresh_token")

    assert result.access_token == "refreshed_token"
    assert result.refresh_token == "new_refresh"
    assert result.expires_in == 7200


# ---------------------------------------------------------------------------
# 4. Category query + caching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_get_categories_cached(_fake_settings):
    """Categories should be fetched once and cached on subsequent calls."""
    categories_data = [
        {"id": "50000001", "name": "Fashion", "children": []},
        {"id": "50000002", "name": "Electronics", "children": []},
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = categories_data

    call_count = 0

    async def _mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(side_effect=_mock_get)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result1 = await get_categories("test_token")
        result2 = await get_categories("test_token")

    assert result1 == categories_data
    assert result2 == categories_data
    assert call_count == 1  # Only called API once — second was cached


# ---------------------------------------------------------------------------
# 5. Duplicate product name (API returns error)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_publish_duplicate_product_name(_fake_settings, adapter, valid_credentials):
    """publish should return failure when product name already exists."""
    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.json.return_value = {
        "code": "DUPLICATE_PRODUCT",
        "message": "Product with the same name already exists",
    }

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[],
            options={
                "product_name": "Duplicate Product",
                "price": 10000,
                "stock_quantity": 50,
                "category_id": "50000001",
            },
            credentials=valid_credentials,
        )

    assert result.success is False
    assert "Naver Commerce" in (result.error or "")


# ---------------------------------------------------------------------------
# 6. Image URL validation
# ---------------------------------------------------------------------------

def test_validate_image_url_accepts_valid():
    """Valid HTTPS image URLs should pass validation."""
    assert _validate_image_url("https://cdn.example.com/photo.jpg") is True
    assert _validate_image_url("https://img.naver.com/product.png") is True
    assert _validate_image_url("https://example.com/hero.webp") is True


def test_validate_image_url_rejects_invalid():
    """Non-HTTPS or non-image URLs should fail validation."""
    assert _validate_image_url("http://insecure.com/img.jpg") is False
    assert _validate_image_url("https://example.com/doc.pdf") is False
    assert _validate_image_url("ftp://files.com/img.png") is False


@pytest.mark.asyncio()
async def test_publish_rejects_invalid_image_url(_fake_settings, adapter, valid_credentials):
    """publish should fail when media contains an invalid image URL."""
    result = await adapter.publish(
        text=None,
        media=[MediaSpec(url="http://insecure.com/bad.jpg", media_type="image")],
        options={
            "product_name": "Bad Image Product",
            "price": 5000,
            "stock_quantity": 10,
            "category_id": "50000001",
        },
        credentials=valid_credentials,
    )
    assert result.success is False
    assert "Invalid image URL" in (result.error or "")


# ---------------------------------------------------------------------------
# 7. Stock update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_update_stock(_fake_settings, adapter, valid_credentials):
    """update_stock should PATCH the stock quantity."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"stockQuantity": 200}

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.patch = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.update_stock("12345", 200, valid_credentials)

    assert result["stockQuantity"] == 200


# ---------------------------------------------------------------------------
# 8. Product deletion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_delete_product(_fake_settings, adapter, valid_credentials):
    """delete should send SUSPENSION status and return True."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"statusType": "SUSPENSION"}

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.put = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.delete("12345", valid_credentials)

    assert result is True


# ---------------------------------------------------------------------------
# 9. Rate limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_publish_rate_limit(_fake_settings, adapter, valid_credentials):
    """publish should return failure when rate limited (429)."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"message": "Too many requests"}

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.publish(
            text=None,
            media=[],
            options={
                "product_name": "Rate Limited Product",
                "price": 10000,
                "stock_quantity": 10,
                "category_id": "50000001",
            },
            credentials=valid_credentials,
        )

    assert result.success is False
    assert "Rate limit" in (result.error or "")


# ---------------------------------------------------------------------------
# 10. Async get_product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_get_product(_fake_settings, adapter, valid_credentials):
    """get_product should fetch product details by ID."""
    product_data = {
        "channelProductNo": "12345",
        "name": "Test Product",
        "salePrice": 15000,
        "stockQuantity": 100,
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = product_data

    with patch("app.adapters.naver_smart_store.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await adapter.get_product("12345", valid_credentials)

    assert result["name"] == "Test Product"
    assert result["salePrice"] == 15000


# ---------------------------------------------------------------------------
# 11. Signature verification
# ---------------------------------------------------------------------------

def test_signature_generation_and_verification():
    """generate_signature and verify_signature should be consistent."""
    client_id = "my_client_id"
    client_secret = "my_secret_key"
    timestamp = 1700000000000

    sig = generate_signature(client_id, client_secret, timestamp)

    # Manual check
    expected_base = f"{client_id}_{timestamp}"
    expected_sig = hmac.new(
        client_secret.encode(),
        expected_base.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected_sig

    # verify_signature should accept it
    assert verify_signature(client_id, client_secret, timestamp, sig) is True

    # Wrong signature should fail
    assert verify_signature(client_id, client_secret, timestamp, "wrong_sig") is False


# ---------------------------------------------------------------------------
# 12. bizmember_id mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio()
async def test_get_user_info_extracts_bizmember_id(_fake_settings, provider):
    """get_user_info should extract bizmember_id from seller profile."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "content": {
            "channelNo": 123456,
            "channelId": "ch_abc",
            "channelName": "MyStore",
            "representativeName": "Test Seller",
            "businessType": "INDIVIDUAL",
            "bizMemberId": "biz_member_789",
        },
    }

    with patch("app.oauth.providers.naver_commerce.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        user_info = await provider.get_user_info("test_access_token")

    assert user_info.platform_user_id == "123456"
    assert user_info.handle == "MyStore"
    assert user_info.display_name == "Test Seller"
    assert user_info.metadata["bizmember_id"] == "biz_member_789"
    assert user_info.metadata["channel_id"] == "ch_abc"
    assert user_info.metadata["business_type"] == "INDIVIDUAL"
