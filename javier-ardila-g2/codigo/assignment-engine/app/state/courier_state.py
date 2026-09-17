from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.models import Courier


class CourierState:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._couriers: dict[str, Courier] = {}
        self._assignment_history: dict[str, list[float]] = {}

    async def init_couriers(self, couriers: list[Courier]):
        async with self._lock:
            self._couriers = {c.courier_id: c.model_copy() for c in couriers}
            for c in couriers:
                if c.courier_id not in self._assignment_history:
                    self._assignment_history[c.courier_id] = []

    async def get_couriers(self) -> list[Courier]:
        async with self._lock:
            return [c.model_copy() for c in self._couriers.values()]

    async def get_courier(self, courier_id: str) -> Optional[Courier]:
        async with self._lock:
            c = self._couriers.get(courier_id)
            return c.model_copy() if c else None

    async def assign_order(self, courier_id: str) -> bool:
        async with self._lock:
            c = self._couriers.get(courier_id)
            if not c:
                return False
            if c.active_orders >= c.max_capacity:
                return False
            c.active_orders += 1
            now = datetime.now(timezone.utc).timestamp()
            self._assignment_history.setdefault(courier_id, []).append(now)
            return True

    async def release_order(self, courier_id: str) -> bool:
        async with self._lock:
            c = self._couriers.get(courier_id)
            if not c or c.active_orders <= 0:
                return False
            c.active_orders -= 1
            return True

    async def get_assignment_history(self, courier_id: str) -> list[float]:
        async with self._lock:
            return list(self._assignment_history.get(courier_id, []))

    async def reset(self):
        async with self._lock:
            for c in self._couriers.values():
                c.active_orders = 0
            self._assignment_history = {cid: [] for cid in self._couriers}

    async def reset_all(self):
        async with self._lock:
            self._couriers = {}
            self._assignment_history = {}


courier_state = CourierState()
