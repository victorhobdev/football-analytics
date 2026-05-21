from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = self._clock()
        requests = self._requests[key]
        cutoff = now - window_seconds

        while requests and requests[0] <= cutoff:
            requests.popleft()

        if len(requests) >= limit:
            retry_after = max(1, math.ceil(window_seconds - (now - requests[0])))
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        requests.append(now)
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=max(0, limit - len(requests)),
            retry_after_seconds=0,
        )
