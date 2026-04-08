"""PII classifier and masking tests."""

from __future__ import annotations

from app.core.pii_classifier import (
    classify_field,
    mask_dict,
    mask_for_api_response,
    mask_value,
    scrub_text,
)


def test_classify_high_pii() -> None:
    assert classify_field("email") == "high"
    assert classify_field("phone") == "high"
    assert classify_field("signer_email") == "high"


def test_classify_medium_pii() -> None:
    assert classify_field("name") == "medium"
    assert classify_field("full_name") == "medium"
    assert classify_field("ip") == "medium"
    assert classify_field("stripe_customer_id") == "medium"


def test_classify_low_pii() -> None:
    assert classify_field("user_agent") == "low"


def test_classify_non_pii() -> None:
    assert classify_field("post_id") is None
    assert classify_field("status") is None


def test_mask_high_email() -> None:
    masked = mask_value("user@example.com", "high")
    assert "***" in masked
    assert masked.endswith("@example.com")
    assert masked != "user@example.com"


def test_mask_high_phone() -> None:
    masked = mask_value("+821012345678", "high")
    assert "***" in masked
    assert masked != "+821012345678"


def test_mask_medium() -> None:
    masked = mask_value("John Doe", "medium")
    assert masked.startswith("J")
    assert "***" in masked


def test_mask_low_unchanged() -> None:
    ua = "Mozilla/5.0"
    assert mask_value(ua, "low") == ua


def test_mask_dict_basic() -> None:
    data = {
        "email": "test@example.com",
        "name": "Alice",
        "status": "active",
    }
    masked = mask_dict(data)
    assert masked["email"] != "test@example.com"
    assert "***" in masked["email"]
    assert masked["status"] == "active"


def test_mask_dict_nested() -> None:
    data = {
        "user": {
            "email": "nested@example.com",
            "id": "123",
        },
    }
    masked = mask_dict(data)
    assert "***" in masked["user"]["email"]
    assert masked["user"]["id"] == "123"


def test_mask_dict_allow_fields() -> None:
    data = {"email": "keep@example.com", "name": "Bob"}
    masked = mask_dict(data, allow_fields=frozenset({"email"}))
    assert masked["email"] == "keep@example.com"
    assert "***" in masked["name"]


def test_mask_for_api_response_masks_nested_lists() -> None:
    data = {
        "contacts": [
            {"email": "keepme@example.com", "phone": "+821012345678"},
        ],
    }
    masked = mask_for_api_response(data)
    assert masked["contacts"][0]["email"] != "keepme@example.com"
    assert masked["contacts"][0]["phone"] != "+821012345678"


def test_scrub_text_email() -> None:
    text = "Contact me at user@example.com for details"
    scrubbed = scrub_text(text)
    assert "[EMAIL REDACTED]" in scrubbed
    assert "user@example.com" not in scrubbed


def test_scrub_text_phone() -> None:
    text = "Call +821012345678 now"
    scrubbed = scrub_text(text)
    assert "[PHONE REDACTED]" in scrubbed
    assert "+821012345678" not in scrubbed


def test_scrub_text_ip() -> None:
    text = "Origin IP was 192.168.0.1 during the request"
    scrubbed = scrub_text(text)
    assert "[IP REDACTED]" in scrubbed
    assert "192.168.0.1" not in scrubbed


def test_scrub_text_preserves_normal() -> None:
    text = "No PII here, just normal text."
    assert scrub_text(text) == text
