"""SSRF protection utility for outbound HTTP requests and provider URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.logging_config import get_logger

logger = get_logger(__name__)


def is_ip_blocked(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_localhost: bool = False,
    allow_private: bool = False,
) -> bool:
    """Return True if an IP address is considered an internal/private/reserved target.

    ``allow_private`` is for operator-approved on-premises deployments (a model
    server on the same LAN or tailnet): loopback, RFC 1918 / unique-local and
    carrier-grade-NAT ranges are permitted. Link-local (which includes the
    169.254.169.254 cloud-metadata endpoint), multicast, reserved and
    unspecified addresses stay blocked either way.
    """
    if allow_private:
        return bool(ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)

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


def is_safe_url(url: str, *, allow_localhost: bool = False, allow_private: bool = False) -> bool:
    """Validate that a URL uses safe HTTP/HTTPS schemes and does not target internal IPs.

    Args:
        url: The candidate URL string to test.
        allow_localhost: When True, loopback addresses (127.0.0.1, localhost)
            are allowed (e.g. for self-hosted local Ollama servers).
        allow_private: When True, private-network addresses are allowed too
            (see ``is_ip_blocked``). Only pass this from an operator-controlled
            setting, never from tenant input.

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
        return not is_ip_blocked(ip, allow_localhost=allow_localhost, allow_private=allow_private)
    except ValueError:
        pass

    if host.lower() == "localhost":
        return allow_localhost or allow_private

    # Resolve hostname to all associated IPs and verify each one
    try:
        addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip, allow_localhost=allow_localhost, allow_private=allow_private):
                    logger.warning("SSRF blocked host=%s resolved_ip=%s", host, ip_str)
                    return False
            except ValueError:
                return False
    except Exception as exc:
        logger.warning("SSRF DNS resolution failed for host %s: %s", host, exc)
        return False

    return True


PRIVATE_LLM_HOSTS_ENV = "BIMGUARD_ALLOW_PRIVATE_LLM_HOSTS"


def private_llm_hosts_allowed() -> bool:
    """Whether the operator allows LLM provider base URLs on private networks.

    Off by default: a tenant admin who can register a provider ``api_base`` could
    otherwise point the server at internal services. An on-premises operator who
    runs a model server (Ollama, vLLM, llama.cpp, LM Studio, ...) on their own
    LAN sets ``BIMGUARD_ALLOW_PRIVATE_LLM_HOSTS=true`` for the whole deployment.
    """
    import os

    from app.services.offline_mode import offline_mode_enabled

    # An offline / air-gapped deployment can only reach model servers on its own
    # network, so BIMGUARD_OFFLINE implies the private-host allowance.
    if offline_mode_enabled():
        return True
    return os.environ.get(PRIVATE_LLM_HOSTS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
