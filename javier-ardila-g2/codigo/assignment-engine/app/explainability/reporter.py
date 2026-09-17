from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.models import AssignmentResult, Courier, Order
from app.state.courier_state import courier_state
from app.state.wait_queue import wait_queue


class ExplainabilityReporter:
    async def generate_report(
        self, result: AssignmentResult, order: Optional[Order] = None
    ) -> dict:
        couriers = await courier_state.get_couriers()
        queue_size = await wait_queue.get_size()
        containment_active = await wait_queue.is_containment_active()
        rejected_history = await wait_queue.get_rejected_history()

        report = {
            "order_id": result.order_id,
            "status": result.status,
            "assigned_courier": result.assigned_courier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasons": [r.model_dump() for r in result.reasons],
            "system_state": {
                "queue_size": queue_size,
                "containment_active": containment_active,
                "couriers": [
                    {
                        "courier_id": c.courier_id,
                        "zone": c.zone,
                        "active_orders": c.active_orders,
                        "max_capacity": c.max_capacity,
                        "utilization": f"{c.active_orders}/{c.max_capacity}",
                    }
                    for c in couriers
                ],
            },
        }

        if result.status == "REJECTED":
            report["natural_language_explanation"] = self._generate_nl_explanation(
                result, couriers, queue_size, containment_active
            )

        return report

    def _generate_nl_explanation(
        self,
        result: AssignmentResult,
        couriers: list[Courier],
        queue_size: int,
        containment_active: bool,
    ) -> str:
        parts: list[str] = []
        parts.append(
            f"El pedido {result.order_id} fue RECHAZADO."
        )

        for reason in result.reasons:
            if reason.rule == "surge_window_active":
                parts.append(
                    f"Motivo: ventana de contención activa por saturación. {reason.detail}"
                )
            elif reason.rule == "surge_protection_active":
                parts.append(
                    f"Motivo: protección contra ráfagas activada. {reason.detail}"
                )
            elif reason.rule == "all_couriers_at_capacity":
                parts.append(
                    "Motivo: todos los repartidores están al máximo de su capacidad."
                )
            elif reason.rule == "rate_limited":
                parts.append(
                    f"Motivo: límite de ritmo por repartidor excedido. {reason.detail}"
                )

        full_couriers = [
            c for c in couriers if c.active_orders >= c.max_capacity
        ]
        if full_couriers:
            names = ", ".join(
                f"{c.courier_id} ({c.active_orders}/{c.max_capacity})"
                for c in full_couriers
            )
            parts.append(f"Repartidores saturados: {names}.")

        if containment_active:
            parts.append(
                "El sistema entró en modo de contención temporal para proteger "
                "los pedidos ya aceptados. Los pedidos express siguen encolándose."
            )

        if queue_size > 0:
            parts.append(
                f"Hay {queue_size} pedido(s) en cola de espera."
            )

        parts.append(
            "Recomendación: el cliente puede reintentar en unos minutos "
            "cuando la carga disminuya o cuando expire la ventana de contención."
        )

        return " ".join(parts)

    async def get_rejected_reports(self) -> list[dict]:
        rejected = await wait_queue.get_rejected_history()
        reports = []
        for r in rejected:
            report = {
                "order_id": r["order_id"],
                "timestamp": r["timestamp"],
                "reasons": r["reasons"],
                "natural_language_explanation": (
                    f"El pedido {r['order_id']} fue rechazado. "
                    f"Razones: {', '.join(rea['rule'] for rea in r['reasons'])}."
                ),
            }
            reports.append(report)
        return reports


reporter = ExplainabilityReporter()
