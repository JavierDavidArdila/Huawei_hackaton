from __future__ import annotations

from typing import Optional

from app.config import get_config
from app.models import AssignmentResult, Courier, Order, OrderStatus, Reason
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter


class Assigner:
    async def filter_by_zone(
        self, couriers: list[Courier], pickup_zone: str
    ) -> tuple[list[Courier], list[Courier]]:
        cfg = get_config()
        if not cfg.same_zone_preferred:
            return couriers, []

        same_zone = [c for c in couriers if c.zone == pickup_zone]
        other_zone = [c for c in couriers if c.zone != pickup_zone]
        return same_zone, other_zone

    async def filter_by_capacity(
        self, couriers: list[Courier]
    ) -> tuple[list[Courier], list[Courier]]:
        cfg = get_config()
        if not cfg.capacity_check:
            return couriers, []

        valid = [c for c in couriers if c.active_orders < c.max_capacity]
        full = [c for c in couriers if c.active_orders >= c.max_capacity]
        return valid, full

    async def sort_by_load(self, couriers: list[Courier]) -> list[Courier]:
        cfg = get_config()
        if not cfg.least_loaded:
            return couriers
        return sorted(couriers, key=lambda c: c.active_orders)

    async def check_rate_limit(self, courier_id: str) -> bool:
        cfg = get_config()
        if not cfg.rate_limit_enabled:
            return True
        return await rate_limiter.check_only(courier_id)

    async def assign(self, order: Order, couriers: list[Courier]) -> AssignmentResult:
        cfg = get_config()
        reasons: list[Reason] = []

        all_couriers = await courier_state.get_couriers()
        if not all_couriers:
            await courier_state.init_couriers(couriers)
            all_couriers = await courier_state.get_couriers()

        if not all_couriers:
            reasons.append(Reason(rule="no_couriers", detail="No couriers available"))
            return AssignmentResult(
                order_id=order.order_id,
                status=OrderStatus.QUEUED.value,
                assigned_courier=None,
                reasons=reasons,
            )

        same_zone, other_zone = await self.filter_by_zone(all_couriers, order.pickup_zone)

        if same_zone:
            names = ", ".join(c.courier_id for c in same_zone)
            reasons.append(
                Reason(
                    rule="same_zone_preferred",
                    detail=f"Couriers in pickup_zone={order.pickup_zone}: {names}",
                )
            )
        else:
            reasons.append(
                Reason(
                    rule="same_zone_preferred",
                    detail=f"No couriers in pickup_zone={order.pickup_zone}, considering all zones",
                )
            )

        candidates = same_zone if same_zone else all_couriers

        valid, full = await self.filter_by_capacity(candidates)

        if full:
            full_details = ", ".join(
                f"{c.courier_id} at {c.active_orders}/{c.max_capacity}" for c in full
            )
            reasons.append(
                Reason(rule="capacity_check", detail=f"Skipped (full): {full_details}")
            )

        if not valid:
            if not same_zone and other_zone:
                valid_other, full_other = await self.filter_by_capacity(other_zone)
                if valid_other:
                    valid = valid_other
                    reasons.append(
                        Reason(
                            rule="zone_balancing",
                            detail=f"No capacity in same zone, trying neighboring zones: {', '.join(c.courier_id for c in valid_other)}",
                        )
                    )

        if not valid:
            all_valid, _ = await self.filter_by_capacity(all_couriers)
            if all_valid:
                valid = all_valid
                reasons.append(
                    Reason(
                        rule="zone_balancing",
                        detail=f"No capacity in preferred zone, using all available couriers",
                    )
                )

        if not valid:
            reasons.append(
                Reason(
                    rule="all_couriers_at_capacity",
                    detail="All couriers are at max_capacity, order queued",
                )
            )
            return AssignmentResult(
                order_id=order.order_id,
                status=OrderStatus.QUEUED.value,
                assigned_courier=None,
                reasons=reasons,
            )

        sorted_couriers = await self.sort_by_load(valid)

        chosen: Optional[Courier] = None
        for c in sorted_couriers:
            if await self.check_rate_limit(c.courier_id):
                chosen = c
                break

        if not chosen:
            reasons.append(
                Reason(
                    rule="rate_limited",
                    detail="All valid couriers are rate-limited (sliding window), order queued",
                )
            )
            return AssignmentResult(
                order_id=order.order_id,
                status=OrderStatus.QUEUED.value,
                assigned_courier=None,
                reasons=reasons,
            )

        success = await courier_state.assign_order(chosen.courier_id)
        if not success:
            reasons.append(
                Reason(
                    rule="assignment_failed",
                    detail=f"Could not assign to {chosen.courier_id} (capacity changed)",
                )
            )
            return AssignmentResult(
                order_id=order.order_id,
                status=OrderStatus.QUEUED.value,
                assigned_courier=None,
                reasons=reasons,
            )

        if cfg.rate_limit_enabled:
            await rate_limiter.check_and_record(chosen.courier_id)

        reasons.append(
            Reason(
                rule="capacity_ok",
                detail=f"{chosen.courier_id} at {chosen.active_orders}/{chosen.max_capacity}",
            )
        )
        reasons.append(
            Reason(
                rule="least_loaded",
                detail=f"{chosen.courier_id} chosen ({chosen.active_orders} active orders, lowest among valid)",
            )
        )

        return AssignmentResult(
            order_id=order.order_id,
            status=OrderStatus.ASSIGNED.value,
            assigned_courier=chosen.courier_id,
            reasons=reasons,
        )


assigner = Assigner()
