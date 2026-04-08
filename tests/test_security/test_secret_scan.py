"""Tests for the secret scanner script."""

from __future__ import annotations

from pathlib import Path

from scripts.secret_scan import scan_file


def test_detects_stripe_live_key(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    prefix = "sk" + "_" + "live" + "_"
    secret = prefix + "abc123def456ghi789jkl012"
    f.write_text(f'KEY = "{secret}"\n')
    findings = scan_file(f)
    assert len(findings) == 1
    assert findings[0][0] == "Stripe live key"


def test_detects_aws_key(tmp_path: Path) -> None:
    f = tmp_path / "creds.py"
    f.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    findings = scan_file(f)
    assert any(name == "AWS access key" for name, _, _ in findings)


def test_detects_private_key(tmp_path: Path) -> None:
    f = tmp_path / "key.pem"
    f.write_text("-----BEGIN PRIVATE KEY-----\ndata\n-----END PRIVATE KEY-----\n")
    findings = scan_file(f)
    assert any(name == "Private key header" for name, _, _ in findings)


def test_clean_file_no_findings(tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text('x = 1\nname = "hello"\n')
    findings = scan_file(f)
    assert len(findings) == 0


def test_detects_jwt_token(tmp_path: Path) -> None:
    f = tmp_path / "jwt.py"
    f.write_text(
        'TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig"\n'
    )
    findings = scan_file(f)
    assert any(name == "JWT token" for name, _, _ in findings)
