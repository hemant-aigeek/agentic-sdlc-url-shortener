"""In-process token bucket (AMB-07).

Keyed by API key; enough to demonstrate the control and its 429 contract.
In a deployment this belongs at the gateway (see BACKLOG.md).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from agentic_sdlc.errors import RateLimitedError


@dataclass
class _Bucket:
    tokens: float
    updated: float


@dataclass
class TokenBucketLimiter:
    capacity: int
    refill_per_second: float
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), updated=now)
                self._buckets[key] = bucket
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(
                float(self.capacity), bucket.tokens + elapsed * self.refill_per_second
            )
            bucket.updated = now
            if bucket.tokens < 1.0:
                retry_after = (
                    int((1.0 - bucket.tokens) / self.refill_per_second) + 1
                    if self.refill_per_second > 0
                    else 60
                )
                raise RateLimitedError(
                    "rate limit exceeded for this API key", retry_after=retry_after
                )
            bucket.tokens -= 1.0
