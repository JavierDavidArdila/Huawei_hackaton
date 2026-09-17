import pytest
import pytest_asyncio

from app.models import Courier, Order, OrderStatus
from app.engine.assigner import assigner
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue


@pytest.mark.asyncio
async def test_assign_same_zone_least_loaded(reset_state, sample_couriers, sample_order):
    result = await assigner.assign(sample_order, sample_couriers)

    assert result.status == "ASSIGNED"
    assert result.assigned_courier == "cour_A"
    assert any(r.rule == "same_zone_preferred" for r in result.reasons)
    assert any(r.rule == "capacity_ok" for r in result.reasons)
    assert any(r.rule == "least_loaded" for r in result.reasons)


@pytest.mark.asyncio
async def test_assign_skips_full_courier(reset_state, sample_couriers):
    order = Order(
        order_id="ord_001",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=2.0,
        priority="normal",
        couriers=sample_couriers,
    )
    result = await assigner.assign(order, sample_couriers)

    assert result.assigned_courier != "cour_C"
    assert result.status == "ASSIGNED"


@pytest.mark.asyncio
async def test_assign_queued_when_all_full(reset_state):
    couriers = [
        Courier(courier_id="cour_X", zone="centro", active_orders=3, max_capacity=3),
        Courier(courier_id="cour_Y", zone="centro", active_orders=2, max_capacity=2),
    ]
    order = Order(
        order_id="ord_002",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=1.0,
        priority="normal",
        couriers=couriers,
    )
    result = await assigner.assign(order, couriers)

    assert result.status == "QUEUED"
    assert result.assigned_courier is None
    assert any(r.rule == "all_couriers_at_capacity" for r in result.reasons)


@pytest.mark.asyncio
async def test_assign_updates_active_orders(reset_state, sample_couriers, sample_order):
    result = await assigner.assign(sample_order, sample_couriers)
    assert result.status == "ASSIGNED"

    couriers = await courier_state.get_couriers()
    assigned = next(c for c in couriers if c.courier_id == result.assigned_courier)
    assert assigned.active_orders >= 2


@pytest.mark.asyncio
async def test_assign_no_couriers(reset_state):
    order = Order(
        order_id="ord_003",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=1.0,
        priority="normal",
        couriers=[],
    )
    result = await assigner.assign(order, [])
    assert result.status == "QUEUED"


@pytest.mark.asyncio
async def test_assign_prefers_same_zone_over_other(reset_state):
    couriers = [
        Courier(courier_id="cour_same", zone="centro", active_orders=0, max_capacity=3),
        Courier(courier_id="cour_other", zone="norte", active_orders=0, max_capacity=3),
    ]
    order = Order(
        order_id="ord_004",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=2.0,
        priority="normal",
        couriers=couriers,
    )
    result = await assigner.assign(order, couriers)
    assert result.assigned_courier == "cour_same"


@pytest.mark.asyncio
async def test_assign_falls_back_to_other_zone(reset_state):
    couriers = [
        Courier(courier_id="cour_full", zone="centro", active_orders=3, max_capacity=3),
        Courier(courier_id="cour_free", zone="norte", active_orders=0, max_capacity=3),
    ]
    order = Order(
        order_id="ord_005",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=2.0,
        priority="normal",
        couriers=couriers,
    )
    result = await assigner.assign(order, couriers)
    assert result.status == "ASSIGNED"
    assert result.assigned_courier == "cour_free"
