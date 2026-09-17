from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.models import Order


class QueuedOrder:
    def __init__(self, order: Order, queued_at: Optional[float] = None):
        self.order = order
        self.queued_at = queued_at or datetime.now(timezone.utc).timestamp()


class WaitQueue:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._queue: list[QueuedOrder] = []
        self._consecutive_full_count: int = 0
        self._containment_active: bool = False
        self._containment_expires_at: float = 0.0
        self._rejected_history: list[dict] = []

    async def enqueue(self, order: Order) -> int:
        async with self._lock:
            self._queue.append(QueuedOrder(order))
            return len(self._queue)

    async def dequeue(self) -> Optional[QueuedOrder]:
        async with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None

    async def get_size(self) -> int:
        async with self._lock:
            return len(self._queue)

    async def increment_full_count(self) -> int:
        async with self._lock:
            self._consecutive_full_count += 1
            return self._consecutive_full_count

    async def reset_full_count(self):
        async with self._lock:
            self._consecutive_full_count = 0

    async def get_full_count(self) -> int:
        async with self._lock:
            return self._consecutive_full_count

    async def activate_containment(self, duration_seconds: int = 120):
        async with self._lock:
            self._containment_active = True
            self._containment_expires_at = (
                datetime.now(timezone.utc).timestamp() + duration_seconds
            )

    async def is_containment_active(self) -> bool:
        async with self._lock:
            if not self._containment_active:
                return False
            now = datetime.now(timezone.utc).timestamp()
            if now >= self._containment_expires_at:
                self._containment_active = False
                self._consecutive_full_count = 0
                return False
            return True

    async def get_contention_expiry(self) -> float:
        async with self._lock:
            return self._containment_expires_at

    async def record_rejection(self, order_id: str, reasons: list[dict]):
        async with self._lock:
            self._rejected_history.append({
                "order_id": order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reasons": reasons,
            })

    async def get_rejected_history(self) -> list[dict]:
        async with self._lock:
            return list(self._rejected_history)

    async def reset(self):
        async with self._lock:
            self._queue = []
            self._consecutive_full_count = 0
            self._containment_active = False
            self._containment_expires_at = 0.0
            self._rejected_history = []


wait_queue = WaitQueue()
