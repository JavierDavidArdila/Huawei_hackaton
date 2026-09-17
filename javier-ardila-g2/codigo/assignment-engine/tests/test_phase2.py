import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone

from app.models import Courier, Order, OrderStatus
from app.engine.assigner import assigner
from app.engine.burst_control import burst_controller
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue


@pytest.mark.asyncio
async def test_sliding_window_rate_limit(reset_state):
    from app.state.rate_limiter import SlidingWindowRateLimiter

    rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)

    assert await rl.check_and_record("cour_A") is True
    assert await rl.check_and_record("cour_A") is True
    assert await rl.check_and_record("cour_A") is True
    assert await rl.check_and_record("cour_A") is False
    assert await rl.check_and_record("cour_B") is True


@pytest.mark.asyncio
async def test_contention_rejects_normal_orders(reset_state, sample_couriers):
    await courier_state.init_couriers(sample_couriers)

    await wait_queue.activate_containment(120)

    order = Order(
        order_id="ord_reject",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=1.0,
        priority="normal",
        couriers=sample_couriers,
    )
    result = await burst_controller.check_contention(order, sample_couriers)

    assert result is not None
    assert result.status == "REJECTED"
    assert any(r.rule == "surge_window_active" for r in result.reasons)


@pytest.mark.asyncio
async def test_contention_allows_express_orders(reset_state, sample_couriers):
    await courier_state.init_couriers(sample_couriers)

    await wait_queue.activate_containment(120)

    order = Order(
        order_id="ord_express",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=1.0,
        priority="express",
        couriers=sample_couriers,
    )
    result = await burst_controller.check_contention(order, sample_couriers)

    assert result is None


@pytest.mark.asyncio
async def test_contention_auto_expires(reset_state):
    await wait_queue.activate_containment(1)
    assert await wait_queue.is_containment_active() is True

    await asyncio.sleep(1.5)
    assert await wait_queue.is_containment_active() is False


@pytest.mark.asyncio
async def test_saturation_triggers_contention(reset_state):
    couriers = [
        Courier(courier_id="cour_X", zone="centro", active_orders=3, max_capacity=3),
    ]

    from app.models import AssignmentResult, Reason
    queued_result = AssignmentResult(
        order_id="ord_test",
        status="QUEUED",
        assigned_courier=None,
        reasons=[Reason(rule="all_couriers_at_capacity", detail="all full")],
    )

    order = Order(
        order_id="ord_test",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=1.0,
        priority="normal",
        couriers=couriers,
    )

    for i in range(3):
        order_i = order.model_copy(update={"order_id": f"ord_{i}"})
        result = await burst_controller.evaluate_saturation(order_i, couriers, queued_result)

    assert await wait_queue.is_containment_active() is True
