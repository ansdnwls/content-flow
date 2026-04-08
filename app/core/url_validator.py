"""SSRF defense — validate external URLs before server-side requests."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def _is_private_ip(host: str) -> bool:
    """Return True if *host* resolves to a private/loopback/link-local address."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


def _is_blocked_hostname(hostname: str) -> bool:
    lower = hostname.lower().rstrip(".")
    if lower in ("localhost", "localhost.localdomain"):
        return True
    if lower.endswith(".local"):
        return True
    if lower.endswith(".internal"):
        return True
    return False


def validate_external_url(url: str) -> bool:
    """Validate that *url* is a safe external HTTP(S) URL.

    Returns True if valid, False if the URL should be rejected.
    Checks:
    - Only http/https schemes
    - No private/loopback/link-local IPs
    - No localhost or *.local hostnames
    - DNS resolution re-check (DNS rebinding defense)
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    if _is_blocked_hostname(hostname):
        return False

    if _is_private_ip(hostname):
        return False

    # DNS resolution check — defend against DNS rebinding
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    for _family, _type, _proto, _canonname, sockaddr in resolved:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            return False

    return True
