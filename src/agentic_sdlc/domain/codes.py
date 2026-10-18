"""Short-code generation (FR-U04, ADR-004).

Random base62 from the OS CSPRNG: not derivable from the target URL or the
insertion order, URL-safe without encoding. Collision handling is the caller's
job (bounded regeneration in ``ShortenerService``); at 7 characters the space
is 62**7 ≈ 3.5e12, so collisions are rare but not impossible, and the service
treats a unique-constraint violation as "try again".
"""

from __future__ import annotations

import secrets

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
MIN_LENGTH = 4
_ALPHABET_SET = frozenset(ALPHABET)


def generate_code(length: int = 7) -> str:
    if length < MIN_LENGTH:
        raise ValueError(f"code length must be at least {MIN_LENGTH}")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_code(code: str, length: int) -> bool:
    return len(code) == length and set(code) <= _ALPHABET_SET
