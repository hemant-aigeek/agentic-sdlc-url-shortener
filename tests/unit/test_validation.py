"""FR-U02 / FR-U03 / NFR-01: target URL validation and private-range rejection."""

from __future__ import annotations

import pytest

from agentic_sdlc.domain.validation import UrlPolicy, validate_target_url
from agentic_sdlc.errors import ValidationError

policy = UrlPolicy(
    max_length=2048,
    blocked_hostnames=("localhost", "metadata.google.internal"),
    blocked_hostname_suffixes=(".localhost", ".internal", ".local"),
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.mark.req("FR-U02")
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/path?q=1",
        "http://example.com",
        "https://sub.example.org:8443/a/b#frag",
        "https://93.184.216.34/",
        "https://[2606:2800:220:1:248:1893:25c8:1946]/",
    ],
)
def test_accepts_public_http_and_https(url: str) -> None:
    assert validate_target_url(url, policy).startswith(("http://", "https://"))


@pytest.mark.req("FR-U02")
def test_normalises_scheme_and_host_case_but_keeps_path_case() -> None:
    assert validate_target_url("HTTPS://Example.COM/Path", policy) == "https://example.com/Path"


@pytest.mark.req("FR-U02")
def test_strips_surrounding_whitespace() -> None:
    assert validate_target_url("  https://example.com  ", policy) == "https://example.com"


@pytest.mark.req("FR-U02")
@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,hi",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "mailto:a@example.com",
        "//example.com/protocol-relative",
        "example.com/no-scheme",
        "/relative/path",
        "",
        "   ",
        "https://",
        "https:///no-host",
        "https://exa mple.com/",
    ],
)
def test_rejects_disallowed_scheme_or_shape(url: str) -> None:
    with pytest.raises(ValidationError) as exc:
        validate_target_url(url, policy)
    assert exc.value.field == "target_url"


@pytest.mark.req("FR-U02")
def test_rejects_over_length() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_target_url("https://example.com/" + "a" * 2048, policy)
    assert "length" in exc.value.detail


@pytest.mark.req("FR-U03")
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.1.2.3/",
        "http://0.0.0.0/",
        "http://10.0.0.5/",
        "http://172.16.4.4/",
        "http://172.31.255.255/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fc00::1]/",
        "http://[fd12::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://017700000001/",
        # abbreviated numeric forms that curl/browsers expand to 127.0.0.1 (found in review)
        "http://127.1/",
        "http://127.0.1/",
        "http://0x7f.1/",
        "http://0177.0.0.1/",
        "http://10.1/",
    ],
)
def test_rejects_loopback_private_linklocal_metadata(url: str) -> None:
    with pytest.raises(ValidationError) as exc:
        validate_target_url(url, policy)
    assert "not allowed" in exc.value.detail


@pytest.mark.req("FR-U03")
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://LOCALHOST:8080/",
        "http://api.localhost/",
        "http://db.internal/",
        "http://printer.local/",
        "http://metadata.google.internal/computeMetadata/v1/",
        # fully-qualified (trailing-dot) spellings of the same names (found in review)
        "http://localhost./",
        "http://metadata.google.internal./",
    ],
)
def test_rejects_blocked_hostnames(url: str) -> None:
    with pytest.raises(ValidationError):
        validate_target_url(url, policy)


@pytest.mark.req("FR-U02")
def test_rejects_credentials_in_url() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_target_url("https://user:pass@example.com/", policy)
    assert "credentials" in exc.value.detail
