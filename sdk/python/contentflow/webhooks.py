"""Webhook signature verification helpers for the ContentFlow Python SDK."""

from __future__ import annotations

import hmac
import time
from hashlib import sha256

SIGNATURE_PREFIX = "sha256="


def verify_signature(
    payload: str | bytes,
    signature: str,
    secret: str,
    timestamp: str,
    *,
    tolerance_seconds: int = 300,
    current_time: int | None = None,
) -> bool:
    """Return ``True`` when the webhook signature and timestamp are valid."""
    if not signature.startswith(SIGNATURE_PREFIX):
        return False

    try:
        signed_at = int(timestamp)
    except (TypeError, ValueError):
        return False

    now = current_time if current_time is not None else int(time.time())
    if abs(now - signed_at) > tolerance_seconds:
        return False

    body = payload.encode() if isinstance(payload, str) else payload
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body,
        sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, f"{SIGNATURE_PREFIX}{expected}")
