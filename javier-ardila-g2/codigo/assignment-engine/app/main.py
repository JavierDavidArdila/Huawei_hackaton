from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_config, update_config
from app.models import (
    AssignmentResult,
    BatchAssignmentResult,
    BatchOrderRequest,
    Courier,
    Order,
    OrderStatus,
    Reason,
)
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue
from app.engine.assigner import assigner
from app.engine.burst_control import burst_controller
from app.engine.optimizer import optimizer
from app.engine.batch_optimizer import batch_optimizer
from app.explainability.reporter import reporter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from app.resilience.pricing_client import pricing_client
    await pricing_client.close()


app = FastAPI(
    title="FlowMatch Assignment Engine",
    description="Motor de asignación en tiempo real para QuickBite",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/assign", response_model=AssignmentResult)
async def assign_order(order: Order):
    if not order.couriers:
        raise HTTPException(status_code=400, detail="No couriers provided in order")

    existing = await courier_state.get_couriers()
    if not existing:
        await courier_state.init_couriers(order.couriers)

    current_couriers = await courier_state.get_couriers()

    contention_result = await burst_controller.check_contention(order, current_couriers)
    if contention_result is not None:
        result = await optimizer.enrich_result(contention_result, order)
        return result

    result = await assigner.assign(order, current_couriers)

    result = await burst_controller.evaluate_saturation(order, current_couriers, result)

    if result.status == OrderStatus.ASSIGNED.value:
        result = await optimizer.enrich_result(result, order)

    return result


@app.post("/assign-batch", response_model=BatchAssignmentResult)
async def assign_batch(request: BatchOrderRequest):
    if request.orders and request.couriers:
        result = await batch_optimizer.assign_batch_optimal(
            request.orders, request.couriers
        )
        return result
    return BatchAssignmentResult(results=[], total_cost=0, strategy="optimal_hungarian")


@app.post("/assign-batch/compare")
async def compare_batch_strategies(request: BatchOrderRequest):
    if not request.orders or not request.couriers:
        raise HTTPException(status_code=400, detail="Orders and couriers required")
    return await batch_optimizer.compare_strategies(request.orders, request.couriers)


@app.get("/couriers", response_model=list[Courier])
async def get_couriers():
    return await courier_state.get_couriers()


@app.post("/couriers/reset")
async def reset_couriers():
    await courier_state.reset()
    await rate_limiter.reset()
    await wait_queue.reset()
    return {"message": "State reset successfully"}


@app.post("/couriers/init")
async def init_couriers(couriers: list[Courier]):
    await courier_state.init_couriers(couriers)
    return {"message": f"Initialized {len(couriers)} couriers"}


@app.get("/config")
async def get_current_config():
    return get_config().model_dump()


@app.put("/config")
async def update_current_config(config_updates: dict):
    return update_config(**config_updates)


@app.get("/explanation/{order_id}")
async def get_explanation(order_id: str):
    rejected = await wait_queue.get_rejected_history()
    for r in rejected:
        if r["order_id"] == order_id:
            return {
                "order_id": order_id,
                "timestamp": r["timestamp"],
                "reasons": r["reasons"],
                "natural_language_explanation": (
                    f"El pedido {order_id} fue rechazado. "
                    f"Razones: {', '.join(rea['rule'] for rea in r['reasons'])}. "
                    f"Detalle: {', '.join(rea['detail'] for rea in r['reasons'])}."
                ),
            }
    raise HTTPException(status_code=404, detail=f"No rejection record for order {order_id}")


@app.get("/explanations/rejected")
async def get_all_rejected_explanations():
    return await reporter.get_rejected_reports()


@app.get("/queue")
async def get_queue_status():
    return {
        "size": await wait_queue.get_size(),
        "containment_active": await wait_queue.is_containment_active(),
        "consecutive_full_count": await wait_queue.get_full_count(),
    }


@app.get("/health")
async def health_check():
    from app.resilience.circuit_breaker import circuit_breaker
    return {
        "status": "healthy",
        "circuit_breaker_state": (await circuit_breaker.get_state()).value,
        "circuit_failure_count": await circuit_breaker.get_failure_count(),
        "queue_size": await wait_queue.get_size(),
        "containment_active": await wait_queue.is_containment_active(),
    }


@app.get("/")
async def root():
    return {
        "service": "FlowMatch Assignment Engine",
        "version": "1.0.0",
        "endpoints": [
            "POST /assign",
            "POST /assign-batch",
            "POST /assign-batch/compare",
            "GET /couriers",
            "POST /couriers/reset",
            "GET /config",
            "PUT /config",
            "GET /explanation/{order_id}",
            "GET /explanations/rejected",
            "GET /queue",
            "GET /health",
        ],
    }
