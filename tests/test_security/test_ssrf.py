"""SSRF defense tests — validate_external_url rejects internal targets."""

from __future__ import annotations

import pytest

from app.core.url_validator import validate_external_url


class TestValidateExternalUrl:
    """Ensure private IPs, localhost, and non-HTTP schemes are blocked."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin",
        "http://127.0.0.1:8080/",
        "http://0.0.0.0/",
        "http://10.0.0.1/secret",
        "http://172.16.0.1/internal",
        "http://192.168.1.1/router",
        "http://[::1]/admin",
    ])
    def test_rejects_private_ips(self, url: str) -> None:
        assert validate_external_url(url) is False

    @pytest.mark.parametrize("url", [
        "http://localhost/admin",
        "http://localhost:3000/",
        "http://service.local/api",
        "http://internal.local/",
        "http://db.internal/query",
    ])
    def test_rejects_blocked_hostnames(self, url: str) -> None:
        assert validate_external_url(url) is False

    @pytest.mark.parametrize("url", [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://evil.com/",
        "javascript:alert(1)",
        "data:text/html,<h1>hi</h1>",
    ])
    def test_rejects_non_http_schemes(self, url: str) -> None:
        assert validate_external_url(url) is False

    def test_rejects_empty_url(self) -> None:
        assert validate_external_url("") is False

    def test_rejects_no_hostname(self) -> None:
        assert validate_external_url("http:///path") is False

    def test_accepts_valid_external_https(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.core.url_validator.socket.getaddrinfo",
            lambda *a, **kw: [(2, 1, 6, "", ("93.184.215.14", 0))],
        )
        assert validate_external_url("https://hooks.example.com/webhook") is True

    def test_accepts_valid_external_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.core.url_validator.socket.getaddrinfo",
            lambda *a, **kw: [(2, 1, 6, "", ("93.184.215.14", 0))],
        )
        assert validate_external_url("http://api.example.com/callback") is True
