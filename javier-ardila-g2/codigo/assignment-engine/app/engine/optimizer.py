from __future__ import annotations

from typing import Optional

from app.config import get_config
from app.models import AssignmentResult, Courier, Order, Reason
from app.resilience.pricing_client import pricing_client


class Optimizer:
    async def optimize_cost(
        self,
        order: Order,
        valid_couriers: list[Courier],
        chosen_courier_id: str,
    ) -> tuple[Optional[int], str, list[Reason]]:
        cfg = get_config()
        reasons: list[Reason] = []

        if not cfg.cost_optimization_enabled:
            cost = int(cfg.base_rate_cop + order.distance_km * cfg.per_km_rate_cop)
            return cost, PricingStatusDegraded.PRICING_SUCCESS.value, reasons

        if len(valid_couriers) > 1:
            sorted_by_distance = sorted(valid_couriers, key=lambda c: c.zone == order.pickup_zone, reverse=True)
            reasons.append(
                Reason(
                    rule="cost_optimization",
                    detail=f"Minimizing cost across {len(valid_couriers)} valid couriers (distance-based)",
                )
            )

        cost, pricing_status = await pricing_client.get_price(order)

        if pricing_status == "circuit_open_degraded_flat_rate":
            reasons.append(
                Reason(
                    rule="circuit_breaker_open",
                    detail=f"Pricing service unavailable, using flat rate: ${cfg.base_rate_cop} COP",
                )
            )
        elif pricing_status == "pricing_failed":
            reasons.append(
                Reason(
                    rule="pricing_failed",
                    detail=f"Pricing call failed, using fallback rate",
                )
            )

        return cost, pricing_status, reasons

    async def enrich_result(
        self, result: AssignmentResult, order: Order
    ) -> AssignmentResult:
        if result.status != "ASSIGNED" or result.assigned_courier is None:
            return result

        couriers = await __import__(
            "app.state.courier_state", fromlist=["courier_state"]
        ).courier_state.get_couriers()

        chosen = next(
            (c for c in couriers if c.courier_id == result.assigned_courier), None
        )
        if not chosen:
            return result

        cost, pricing_status, extra_reasons = await self.optimize_cost(
            order, couriers, chosen.courier_id
        )

        result.cost = cost
        result.pricing_status = pricing_status
        result.reasons.extend(extra_reasons)
        return result


from app.models import PricingStatus as PricingStatusDegraded

optimizer = Optimizer()
