"""SSRF protection utility for outbound HTTP requests and provider URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.logging_config import get_logger

logger = get_logger(__name__)


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_localhost: bool = False) -> bool:
    """Return True if an IP address is considered an internal/private/reserved target."""
    if allow_localhost and ip.is_loopback:
        return False

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    # Explicit check for 169.254.169.254 and cloud metadata ranges
    if isinstance(ip, ipaddress.IPv4Address):
        # 169.254.0.0/16 is link-local, but explicit safety check
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            return True
        # 100.64.0.0/10 (Carrier-grade NAT)
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            return True

    return False


def is_safe_url(url: str, *, allow_localhost: bool = False) -> bool:
    """Validate that a URL uses safe HTTP/HTTPS schemes and does not target internal IPs.

    Args:
        url: The candidate URL string to test.
        allow_localhost: When True, loopback addresses (127.0.0.1, localhost)
            are allowed (e.g. for self-hosted local Ollama servers).

    Returns:
        True if the URL is safe to query; False otherwise.

    Note:
        This is a check-then-use validation: the hostname is resolved here,
        but the caller's own HTTP client resolves it again independently when
        it actually connects. A hostname with a short-TTL DNS record could in
        principle resolve safely here and to an internal address moments
        later (DNS rebinding). Full protection would require pinning the
        connection to the IP validated here (e.g. a custom transport), which
        is not implemented. Callers that need stronger guarantees should
        additionally restrict egress at the network layer.
    """
    if not url or not isinstance(url, str):
        return False

    clean = url.strip()
    try:
        parsed = urlparse(clean)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.hostname
    if not host:
        return False

    host = host.strip("[]")

    # Check literal IP address
    try:
        ip = ipaddress.ip_address(host)
        return not is_ip_blocked(ip, allow_localhost=allow_localhost)
    except ValueError:
        pass

    if host.lower() == "localhost":
        return allow_localhost

    # Resolve hostname to all associated IPs and verify each one
    try:
        addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip, allow_localhost=allow_localhost):
                    logger.warning("SSRF blocked host=%s resolved_ip=%s", host, ip_str)
                    return False
            except ValueError:
                return False
    except Exception as exc:
        logger.warning("SSRF DNS resolution failed for host %s: %s", host, exc)
        return False

    return True
