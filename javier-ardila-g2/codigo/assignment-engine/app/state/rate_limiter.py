from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Optional


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 3, window_seconds: int = 10):
        self._lock = asyncio.Lock()
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: dict[str, deque] = {}

    async def check_and_record(self, key: str) -> bool:
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            if key not in self._timestamps:
                self._timestamps[key] = deque()

            dq = self._timestamps[key]
            cutoff = now - self._window_seconds
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= self._max_requests:
                return False

            dq.append(now)
            return True

    async def check_only(self, key: str) -> bool:
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            if key not in self._timestamps:
                return True

            dq = self._timestamps[key]
            cutoff = now - self._window_seconds
            while dq and dq[0] < cutoff:
                dq.popleft()

            return len(dq) < self._max_requests

    async def get_count(self, key: str) -> int:
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            if key not in self._timestamps:
                return 0
            dq = self._timestamps[key]
            cutoff = now - self._window_seconds
            while dq and dq[0] < cutoff:
                dq.popleft()
            return len(dq)

    async def reset(self):
        async with self._lock:
            self._timestamps = {}


rate_limiter = SlidingWindowRateLimiter()
