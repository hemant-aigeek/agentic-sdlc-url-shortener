"""Per-stage reliability policies (FR-O08, FR-O09, FR-G04, ADR-008)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.1
    multiplier: float = 2.0
    max_delay_s: float = 2.0

    def delay_for(self, attempt: int) -> float:
        """Delay before ``attempt`` (1-based) — exponential, capped."""
        if attempt <= 1:
            return 0.0
        return min(self.max_delay_s, self.base_delay_s * (self.multiplier ** (attempt - 2)))

    def can_retry(self, attempts_so_far: int) -> bool:
        return attempts_so_far < self.max_attempts


@dataclass(frozen=True)
class TimeoutPolicy:
    seconds: float = 5.0


@dataclass(frozen=True)
class GatePolicy:
    timeout_s: float | None = None  # None: wait for a human indefinitely


NO_RETRY = RetryPolicy(max_attempts=1)
