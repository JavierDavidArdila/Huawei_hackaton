from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 15,
    ):
        self._lock = asyncio.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

    async def call(self, func, *args, **kwargs):
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                else:
                    return None, CircuitState.OPEN

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                self._success_count += 1
            return result, self._state

        except Exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
                elif self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN

            return None, self._state

    async def get_state(self) -> CircuitState:
        async with self._lock:
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                return CircuitState.HALF_OPEN
            return self._state

    async def get_failure_count(self) -> int:
        async with self._lock:
            return self._failure_count

    async def reset(self):
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return False
        return time.time() - self._last_failure_time >= self._recovery_timeout


circuit_breaker = CircuitBreaker()
