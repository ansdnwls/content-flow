"""PII classification and automatic masking for logs and API responses."""

from __future__ import annotations

import re
from typing import Any

PII_FIELDS: dict[str, str] = {
    "email": "high",
    "name": "medium",
    "full_name": "medium",
    "ip_address": "medium",
    "ip": "medium",
    "user_agent": "low",
    "stripe_customer_id": "medium",
    "phone": "high",
    "social_account_username": "medium",
    "handle": "medium",
    "display_name": "medium",
    "company": "medium",
    "signer_name": "medium",
    "signer_email": "high",
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\+?[1-9]\d{7,14}")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def classify_field(field_name: str) -> str | None:
    """Return the PII sensitivity level for a field name, or None."""
    return PII_FIELDS.get(field_name.lower())


def mask_value(value: str, sensitivity: str) -> str:
    """Mask a PII value based on sensitivity level."""
    if not value:
        return value
    if sensitivity == "high":
        if "@" in value:
            local, domain = value.split("@", 1)
            masked_local = local[0] + "***" if local else "***"
            return f"{masked_local}@{domain}"
        if len(value) <= 4:
            return "***"
        return value[:2] + "***" + value[-2:]
    if sensitivity == "medium":
        if len(value) <= 2:
            return "***"
        return value[:1] + "***" + value[-1:]
    return value


def mask_object(
    value: Any,
    *,
    field_name: str | None = None,
    allow_fields: frozenset[str] | None = None,
) -> Any:
    """Recursively mask dict/list payloads using field names as the signal."""
    if isinstance(value, dict):
        return mask_dict(value, allow_fields=allow_fields)
    if isinstance(value, list):
        return [
            mask_object(item, field_name=field_name, allow_fields=allow_fields)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            mask_object(item, field_name=field_name, allow_fields=allow_fields)
            for item in value
        )
    if field_name and isinstance(value, str):
        sensitivity = classify_field(field_name)
        if sensitivity:
            return mask_value(value, sensitivity)
    return value


def mask_dict(
    data: dict[str, Any],
    *,
    allow_fields: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return a new dict with PII fields masked.

    If *allow_fields* is provided, those fields are left unmasked.
    """
    masked: dict[str, Any] = {}
    for key, value in data.items():
        if allow_fields and key in allow_fields:
            masked[key] = value
            continue

        masked[key] = mask_object(value, field_name=key, allow_fields=allow_fields)
    return masked


def mask_for_api_response(
    data: Any,
    *,
    is_admin: bool = False,
    allow_fields: frozenset[str] | None = None,
) -> Any:
    """Mask API payloads for non-admin responses."""
    if is_admin:
        return data
    return mask_object(data, allow_fields=allow_fields)


def scrub_text(text: str) -> str:
    """Remove email addresses and phone numbers from free text."""
    scrubbed = _EMAIL_RE.sub("[EMAIL REDACTED]", text)
    scrubbed = _PHONE_RE.sub("[PHONE REDACTED]", scrubbed)
    return _IP_RE.sub("[IP REDACTED]", scrubbed)
