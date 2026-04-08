"""Tests for the secret scanner script.

All test secrets are assembled at runtime from fragments to permanently
avoid GitHub push protection false positives.  The scanner regex in
scripts/secret_scan.py is unchanged -- real leaked secrets are still caught.
"""
from __future__ import annotations

from pathlib import Path

from scripts.secret_scan import scan_file


def _assemble(*parts: str) -> str:
    """Join fragments into a test secret at runtime.

    Splitting secret-shaped strings across multiple literals prevents
    GitHub's static push-protection scanner from flagging this file.
    """
    return "".join(parts)


def test_detects_stripe_live_key(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    secret = _assemble("sk", "_live_", "abc123def456ghi789jkl012")
    f.write_text(f'KEY = "{secret}"\n')
    findings = scan_file(f)
    assert len(findings) == 1
    assert findings[0][0] == "Stripe live key"


def test_detects_aws_key(tmp_path: Path) -> None:
    f = tmp_path / "creds.py"
    secret = _assemble("AKI", "AIOSFODNN7EXAMPLE")
    f.write_text(f'AWS_KEY = "{secret}"\n')
    findings = scan_file(f)
    assert any(name == "AWS access key" for name, _, _ in findings)


def test_detects_private_key(tmp_path: Path) -> None:
    f = tmp_path / "key.pem"
    header = _assemble("-----BEGIN ", "PRIVATE KEY-----")
    footer = _assemble("-----END ", "PRIVATE KEY-----")
    f.write_text(f"{header}\ndata\n{footer}\n")
    findings = scan_file(f)
    assert any(name == "Private key header" for name, _, _ in findings)


def test_clean_file_no_findings(tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text('x = 1\nname = "hello"\n')
    findings = scan_file(f)
    assert len(findings) == 0


def test_detects_jwt_token(tmp_path: Path) -> None:
    f = tmp_path / "jwt.py"
    token = _assemble(
        "eyJhbGciOiJIUzI1NiJ9",
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        ".sig",
    )
    f.write_text(f'TOKEN = "{token}"\n')
    findings = scan_file(f)
    assert any(name == "JWT token" for name, _, _ in findings)
