from __future__ import annotations

import asyncio
import random
from typing import Optional

import httpx

from app.config import get_config
from app.resilience.circuit_breaker import CircuitBreaker, circuit_breaker


class PricingClient:
    def __init__(self):
        self._cb = circuit_breaker
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=3.0)
        return self._client

    async def _call_pricing_service(self, order) -> int:
        cfg = get_config()
        client = await self._get_client()
        url = f"{cfg.pricing_service_url}/price"
        payload = {
            "order_id": order.order_id,
            "distance_km": order.distance_km,
            "priority": order.priority.value,
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("price", cfg.base_rate_cop)

    async def _fallback_price(self, order) -> int:
        cfg = get_config()
        return int(cfg.base_rate_cop + order.distance_km * cfg.per_km_rate_cop)

    async def get_price(self, order) -> tuple[int, str]:
        cfg = get_config()

        result, cb_state = await self._cb.call(self._call_pricing_service, order)

        if result is not None and cb_state.value != "open":
            return result, "pricing_success"

        if cb_state.value == "open":
            fallback = await self._fallback_price(order)
            return fallback, "circuit_open_degraded_flat_rate"

        fallback = await self._fallback_price(order)
        return fallback, "pricing_failed"

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


pricing_client = PricingClient()
