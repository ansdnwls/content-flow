"""HMAC-SHA256 webhook signature verification for yt-factory."""

from __future__ import annotations

import hashlib
import hmac
import time


class SignatureError(Exception):
    """Raised when signature verification fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _build_signed_payload(timestamp: str, body: bytes) -> bytes:
    return f"{timestamp}.".encode() + body


def create_yt_factory_signature(body: bytes, secret: str) -> str:
    """Create a valid signature header value (for testing)."""
    t = str(int(time.time()))
    signed = _build_signed_payload(t, body)
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={t},sha256={digest}"


def verify_yt_factory_signature(
    body: bytes,
    signature_header: str | None,
    secret: str | None,
    tolerance_seconds: int = 300,
) -> None:
    """
    Verify ``X-YtBoost-Signature`` HMAC-SHA256 header.

    Format: ``t=<unix-timestamp>,sha256=<hex-digest>``

    Raises:
        SignatureError: on any verification failure.
    """
    if not secret:
        return  # no secret configured — skip verification

    if not signature_header:
        raise SignatureError("Missing signature header")

    parts: dict[str, str] = {}
    try:
        for segment in signature_header.split(","):
            key, _, value = segment.partition("=")
            if not key or not value:
                raise ValueError
            parts[key.strip()] = value.strip()
    except ValueError:
        raise SignatureError("Malformed signature format") from None

    timestamp = parts.get("t")
    digest = parts.get("sha256")

    if not timestamp or not digest:
        raise SignatureError("Malformed signature format")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise SignatureError("Malformed signature format") from None

    now = int(time.time())
    if abs(now - ts_int) > tolerance_seconds:
        raise SignatureError("Signature timestamp expired")

    expected = hmac.new(
        secret.encode(),
        _build_signed_payload(timestamp, body),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, digest):
        raise SignatureError("Invalid signature")
