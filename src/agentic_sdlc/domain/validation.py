"""Target URL validation (FR-U02, FR-U03).

Pure function over a ``UrlPolicy`` so the rules are testable without the
application. The private-range check is literal-only by decision AMB-03: a
hostname that *resolves* to a private address is not caught here, and that
residual risk is documented rather than hidden.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from agentic_sdlc.errors import ValidationError

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Address ranges a public redirector must never point at.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",  # "this" network
        "10.0.0.0/8",  # RFC 1918
        "100.64.0.0/10",  # CGNAT
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local incl. cloud metadata 169.254.169.254
        "172.16.0.0/12",  # RFC 1918
        "192.0.0.0/24",  # IETF protocol assignments
        "192.168.0.0/16",  # RFC 1918
        "198.18.0.0/15",  # benchmarking
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved
        "64:ff9b::/96",  # NAT64 well-known prefix: embeds an IPv4 address (e.g. loopback)
        "64:ff9b:1::/48",  # local-use NAT64
        "::1/128",  # loopback
        "::/128",  # unspecified
        "fc00::/7",  # ULA
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
    )
]

_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")
_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_NUMERIC_HOST_RE = re.compile(r"^(0x[0-9a-fA-F]+|0[0-7]+|\d+)$")
# every label numeric (decimal / octal / hex) but not a canonical dotted quad:
# "127.1", "0x7f.1", "0177.0.0.1" — expanded to an IPv4 address by libcurl and browsers
_ABBREVIATED_IPV4_RE = re.compile(r"^(?:(?:0x[0-9a-fA-F]+|\d+)\.){1,3}(?:0x[0-9a-fA-F]+|\d+)$")


@dataclass(frozen=True)
class UrlPolicy:
    max_length: int = 2048
    blocked_hostnames: tuple[str, ...] = ("localhost",)
    blocked_hostname_suffixes: tuple[str, ...] = (".localhost", ".internal", ".local")


def validate_target_url(raw: str, policy: UrlPolicy) -> str:
    """Return the normalised URL or raise ``ValidationError(field="target_url")``."""
    url = (raw or "").strip()
    if not url:
        raise ValidationError("target_url is required", field="target_url")
    if len(url) > policy.max_length:
        raise ValidationError(
            f"target_url exceeds maximum length of {policy.max_length}", field="target_url"
        )

    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            f"scheme '{scheme or 'none'}' is not allowed; use http or https", field="target_url"
        )
    if parts.username is not None or parts.password is not None:
        raise ValidationError("credentials in target_url are not allowed", field="target_url")

    host = (parts.hostname or "").lower().rstrip(".")  # "localhost." is the FQDN form of localhost
    if not host:
        raise ValidationError("target_url must include a host", field="target_url")
    if not host.isascii() and ":" not in host:
        try:  # internationalised domain name -> punycode, so "münchen.de" is accepted
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValidationError(
                "target_url host is not a valid domain name", field="target_url"
            ) from exc
    if " " in parts.netloc:
        raise ValidationError("target_url host contains whitespace", field="target_url")

    _reject_blocked_host(host, policy)

    try:
        port = parts.port
    except ValueError as exc:
        raise ValidationError("target_url port is invalid", field="target_url") from exc

    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != {"http": 80, "https": 443}[scheme]:
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


def _reject_blocked_host(host: str, policy: UrlPolicy) -> None:
    address = _as_ip(host)
    if address is not None:
        if address.is_private or address.is_loopback or address.is_link_local:
            raise ValidationError(
                "target_url host is a private, loopback or link-local address, not allowed",
                field="target_url",
            )
        if any(address in net for net in _BLOCKED_NETWORKS):
            raise ValidationError(
                "target_url host is a reserved address, not allowed", field="target_url"
            )
        return

    if not _HOST_RE.match(host):
        raise ValidationError("target_url host contains invalid characters", field="target_url")
    if _ABBREVIATED_IPV4_RE.match(host):
        raise ValidationError(
            "target_url host is an abbreviated numeric address, not allowed",
            field="target_url",
        )
    labels = host.split(".")
    if any(not _LABEL_RE.match(label) for label in labels):
        raise ValidationError("target_url host is not a valid domain name", field="target_url")
    if len(labels) < 2:
        # single-label names ("metadata", "intranet") only resolve on internal networks
        raise ValidationError(
            "target_url host must be a fully qualified domain name", field="target_url"
        )
    if host in policy.blocked_hostnames or host.endswith(policy.blocked_hostname_suffixes):
        raise ValidationError(
            "target_url host is on the blocked hostname list, not allowed", field="target_url"
        )


def _as_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse dotted, bracketed, integer, hex and octal IP literals; None if a hostname."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        mapped = getattr(addr, "ipv4_mapped", None)
        return mapped or addr
    if _NUMERIC_HOST_RE.match(host):
        try:
            if host.startswith("0x"):
                value = int(host, 16)
            elif len(host) > 1 and host.startswith("0"):
                value = int(host, 8)
            else:
                value = int(host)
        except ValueError:
            return None
        if 0 <= value <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(value)
    return None
