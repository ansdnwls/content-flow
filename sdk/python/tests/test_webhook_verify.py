"""Tests for contentflow.webhooks signature verification."""

from __future__ import annotations

import hmac
import time
from hashlib import sha256

from contentflow.webhooks import verify_signature

SECRET = "whsec_test_secret"
BODY = '{"event":"post.published","data":{"id":"p1"}}'


def _sign(body: str, secret: str, timestamp: str) -> str:
    digest = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body.encode(),
        sha256,
    ).hexdigest()
    return f"sha256={digest}"


def test_verify_signature_valid() -> None:
    ts = str(int(time.time()))
    sig = _sign(BODY, SECRET, ts)
    assert verify_signature(BODY, sig, SECRET, ts) is True


def test_verify_signature_invalid() -> None:
    ts = str(int(time.time()))
    assert verify_signature(BODY, "sha256=bad", SECRET, ts) is False


def test_verify_signature_bytes_body() -> None:
    ts = str(int(time.time()))
    sig = _sign(BODY, SECRET, ts)
    assert verify_signature(BODY.encode(), sig, SECRET, ts) is True
