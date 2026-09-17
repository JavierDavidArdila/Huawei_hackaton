from __future__ import annotations

from typing import Optional

import asyncio
from datetime import datetime, timezone

from app.config import get_config
from app.models import (
    AssignmentResult,
    BatchAssignmentResult,
    Courier,
    Order,
    OrderStatus,
    Reason,
)
from app.state.courier_state import courier_state
from app.engine.assigner import assigner


class BatchOptimizer:
    async def assign_batch_greedy(
        self, orders: list[Order], couriers: list[Courier]
    ) -> BatchAssignmentResult:
        await courier_state.init_couriers(couriers)
        results: list[AssignmentResult] = []

        for order in orders:
            order_with_couriers = order.model_copy()
            current_couriers = await courier_state.get_couriers()
            order_with_couriers.couriers = current_couriers
            result = await assigner.assign(order_with_couriers, current_couriers)
            results.append(result)

        total_cost = sum(r.cost or 0 for r in results)
        return BatchAssignmentResult(
            results=results, total_cost=total_cost, strategy="greedy"
        )

    async def assign_batch_optimal(
        self, orders: list[Order], couriers: list[Courier]
    ) -> BatchAssignmentResult:
        await courier_state.init_couriers(couriers)
        all_couriers = await courier_state.get_couriers()

        n_orders = len(orders)
        n_couriers = len(all_couriers)

        if n_orders == 0 or n_couriers == 0:
            return BatchAssignmentResult(
                results=[], total_cost=0, strategy="optimal_hungarian"
            )

        import numpy as np
        from scipy.optimize import linear_sum_assignment

        cost_matrix = np.full((n_orders, n_couriers), float("inf"))

        cfg = get_config()
        for i, order in enumerate(orders):
            for j, courier in enumerate(all_couriers):
                if courier.active_orders >= courier.max_capacity:
                    continue
                zone_penalty = 0 if courier.zone == order.pickup_zone else 500
                load_penalty = courier.active_orders * 200
                distance_cost = order.distance_km * cfg.per_km_rate_cop
                cost_matrix[i][j] = distance_cost + zone_penalty + load_penalty + cfg.base_rate_cop

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        results: list[AssignmentResult] = []
        total_cost = 0

        for i, order in enumerate(orders):
            assigned = False
            for r, c in zip(row_ind, col_ind):
                if r == i and cost_matrix[r][c] != float("inf"):
                    courier = all_couriers[c]
                    success = await courier_state.assign_order(courier.courier_id)
                    if success:
                        cost = int(cost_matrix[r][c])
                        total_cost += cost
                        reasons = [
                            Reason(
                                rule="same_zone_preferred",
                                detail=f"{courier.courier_id} in zone={courier.zone} (order zone={order.pickup_zone})",
                            ),
                            Reason(
                                rule="capacity_ok",
                                detail=f"{courier.courier_id} at {courier.active_orders}/{courier.max_capacity}",
                            ),
                            Reason(
                                rule="optimal_assignment",
                                detail=f"Hungarian algorithm: order {order.order_id} -> {courier.courier_id} (cost={cost})",
                            ),
                        ]
                        results.append(
                            AssignmentResult(
                                order_id=order.order_id,
                                status=OrderStatus.ASSIGNED.value,
                                assigned_courier=courier.courier_id,
                                reasons=reasons,
                                cost=cost,
                                pricing_status="optimal_batch",
                            )
                        )
                        assigned = True
                        break

            if not assigned:
                results.append(
                    AssignmentResult(
                        order_id=order.order_id,
                        status=OrderStatus.QUEUED.value,
                        assigned_courier=None,
                        reasons=[
                            Reason(
                                rule="no_optimal_match",
                                detail="No valid courier found in optimal assignment",
                            )
                        ],
                    )
                )

        return BatchAssignmentResult(
            results=results, total_cost=total_cost, strategy="optimal_hungarian"
        )

    async def compare_strategies(
        self, orders: list[Order], couriers: list[Courier]
    ) -> dict:
        await courier_state.reset()
        greedy_result = await self.assign_batch_greedy(orders, couriers)

        await courier_state.reset()
        optimal_result = await self.assign_batch_optimal(orders, couriers)

        return {
            "greedy": {
                "total_cost": greedy_result.total_cost,
                "assigned": sum(1 for r in greedy_result.results if r.status == "ASSIGNED"),
                "queued": sum(1 for r in greedy_result.results if r.status == "QUEUED"),
            },
            "optimal": {
                "total_cost": optimal_result.total_cost,
                "assigned": sum(1 for r in optimal_result.results if r.status == "ASSIGNED"),
                "queued": sum(1 for r in optimal_result.results if r.status == "QUEUED"),
            },
            "cost_difference": greedy_result.total_cost - optimal_result.total_cost,
            "optimal_better": optimal_result.total_cost <= greedy_result.total_cost,
        }


batch_optimizer = BatchOptimizer()
