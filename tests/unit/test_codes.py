"""FR-U04 / ADR-004: random base62 short codes."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agentic_sdlc.domain.codes import ALPHABET, generate_code, is_valid_code

pytestmark = pytest.mark.unit


@pytest.mark.req("FR-U04")
def test_default_length_is_seven() -> None:
    assert len(generate_code()) == 7


@pytest.mark.req("FR-U04")
def test_alphabet_is_url_safe_base62() -> None:
    assert len(ALPHABET) == 62
    assert set(ALPHABET) == set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


@pytest.mark.req("FR-U04")
def test_codes_use_only_alphabet() -> None:
    for _ in range(1000):
        assert set(generate_code()) <= set(ALPHABET)


@pytest.mark.req("FR-U04")
def test_ten_thousand_codes_are_distinct() -> None:
    codes = {generate_code() for _ in range(10_000)}
    assert len(codes) == 10_000


@pytest.mark.req("FR-U04")
@settings(max_examples=50)
@given(st.integers(min_value=4, max_value=16))
def test_requested_length_is_honoured(length: int) -> None:
    code = generate_code(length)
    assert len(code) == length
    assert is_valid_code(code, length)


@pytest.mark.req("FR-U04")
@pytest.mark.parametrize("bad", ["", "abc", "abc-123", "abcdefg!", "ABCDEFGH", "abc def"])
def test_is_valid_code_rejects_wrong_shape(bad: str) -> None:
    assert not is_valid_code(bad, 7)


@pytest.mark.req("FR-U04")
def test_length_below_minimum_is_refused() -> None:
    with pytest.raises(ValueError, match="length"):
        generate_code(3)
