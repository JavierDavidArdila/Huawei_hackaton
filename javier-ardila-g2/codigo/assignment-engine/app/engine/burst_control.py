from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.config import get_config
from app.models import AssignmentResult, Courier, Order, OrderStatus, Reason
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue


class BurstController:
    async def check_contention(
        self, order: Order, all_couriers: list[Courier]
    ) -> Optional[AssignmentResult]:
        cfg = get_config()
        if not cfg.containment_enabled:
            return None

        if await wait_queue.is_containment_active():
            if order.priority.value == "normal":
                reasons = [
                    Reason(
                        rule="surge_window_active",
                        detail=f"Contention window active, normal orders rejected. Expires in {int(await wait_queue.get_contention_expiry() - datetime.now(timezone.utc).timestamp())}s",
                    )
                ]
                await wait_queue.record_rejection(
                    order.order_id,
                    [r.model_dump() for r in reasons],
                )
                return AssignmentResult(
                    order_id=order.order_id,
                    status=OrderStatus.REJECTED.value,
                    assigned_courier=None,
                    reasons=reasons,
                )
            else:
                return None

        return None

    async def evaluate_saturation(
        self,
        order: Order,
        all_couriers: list[Courier],
        assignment_result: AssignmentResult,
    ) -> AssignmentResult:
        cfg = get_config()
        if not cfg.containment_enabled:
            return assignment_result

        if assignment_result.status == OrderStatus.QUEUED.value:
            all_full = all(
                c.active_orders >= c.max_capacity for c in all_couriers
            )
            queue_size = await wait_queue.get_size()

            if all_full or assignment_result.assigned_courier is None:
                full_count = await wait_queue.increment_full_count()

                if full_count >= cfg.containment_threshold:
                    await wait_queue.activate_containment(
                        cfg.containment_duration_seconds
                    )
                    if order.priority.value == "normal":
                        reasons = [
                            Reason(
                                rule="capacity_ok",
                                detail=f"0 couriers with free capacity",
                            ),
                            Reason(
                                rule="surge_protection_active",
                                detail=f"all couriers full, queue growing for {full_count} orders (window={cfg.containment_duration_seconds}s)",
                            ),
                        ]
                        await wait_queue.record_rejection(
                            order.order_id,
                            [r.model_dump() for r in reasons],
                        )
                        return AssignmentResult(
                            order_id=order.order_id,
                            status=OrderStatus.REJECTED.value,
                            assigned_courier=None,
                            reasons=reasons,
                        )
                    else:
                        await wait_queue.enqueue(order)
                        reasons = assignment_result.reasons + [
                            Reason(
                                rule="surge_protection_active",
                                detail=f"Express order queued despite contention (queue size: {await wait_queue.get_size()})",
                            )
                        ]
                        return AssignmentResult(
                            order_id=order.order_id,
                            status=OrderStatus.QUEUED.value,
                            assigned_courier=None,
                            reasons=reasons,
                        )
                else:
                    await wait_queue.enqueue(order)
                    return assignment_result
        else:
            await wait_queue.reset_full_count()

        return assignment_result

    async def check_courier_rate_limit(
        self, courier_id: str
    ) -> bool:
        cfg = get_config()
        if not cfg.rate_limit_enabled:
            return True
        return await rate_limiter.check_only(courier_id)

    async def record_assignment(self, courier_id: str):
        cfg = get_config()
        if cfg.rate_limit_enabled:
            await rate_limiter.check_and_record(courier_id)


burst_controller = BurstController()
