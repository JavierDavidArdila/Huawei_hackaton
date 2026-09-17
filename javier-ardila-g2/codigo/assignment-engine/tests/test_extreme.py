import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models import Courier, Order
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_order(order_id, zone="centro", distance=1.0, priority="normal"):
    return Order(
        order_id=order_id,
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone=zone,
        distance_km=distance,
        priority=priority,
    )


@pytest.mark.asyncio
async def test_burst_single_zone(reset_state, client):
    couriers = [
        Courier(courier_id="cour_A", zone="centro", active_orders=0, max_capacity=2),
        Courier(courier_id="cour_B", zone="centro", active_orders=0, max_capacity=2),
    ]
    await client.post("/couriers/init", json=[c.model_dump() for c in couriers])

    results = []
    for i in range(6):
        order = make_order(f"ord_burst_{i}", zone="centro")
        order.couriers = couriers
        resp = await client.post("/assign", json=order.model_dump())
        results.append(resp.json())

    assigned = [r for r in results if r["status"] == "ASSIGNED"]
    assert len(assigned) <= 4, "Should not assign more than total capacity"


@pytest.mark.asyncio
async def test_all_couriers_full_at_once(reset_state, client):
    couriers = [
        Courier(courier_id="cour_X", zone="centro", active_orders=3, max_capacity=3),
        Courier(courier_id="cour_Y", zone="centro", active_orders=2, max_capacity=2),
    ]

    order = make_order("ord_full", zone="centro")
    order.couriers = couriers
    resp = await client.post("/assign", json=order.model_dump())
    result = resp.json()

    assert result["status"] in ["QUEUED", "REJECTED"]
    assert result["assigned_courier"] is None


@pytest.mark.asyncio
async def test_avalanche_express_orders(reset_state, client):
    couriers = [
        Courier(courier_id="cour_E", zone="centro", active_orders=0, max_capacity=1),
    ]
    await client.post("/couriers/init", json=[c.model_dump() for c in couriers])

    results = []
    for i in range(5):
        order = make_order(f"ord_exp_{i}", zone="centro", priority="express")
        order.couriers = couriers
        resp = await client.post("/assign", json=order.model_dump())
        results.append(resp.json())

    assigned = [r for r in results if r["status"] == "ASSIGNED"]
    assert len(assigned) == 1, "Only 1 express should be assigned (capacity=1)"

    queued = [r for r in results if r["status"] == "QUEUED"]
    assert len(queued) >= 1, "Remaining express orders should be queued, not rejected"


@pytest.mark.asyncio
async def test_negative_distance_rejected(reset_state, client):
    couriers = [
        Courier(courier_id="cour_A", zone="centro", active_orders=0, max_capacity=3),
    ]

    order_data = {
        "order_id": "ord_neg",
        "timestamp": "2024-11-28T12:58:00Z",
        "pickup_zone": "centro",
        "distance_km": -1.0,
        "priority": "normal",
        "couriers": [c.model_dump() for c in couriers],
    }
    resp = await client.post("/assign", json=order_data)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_priority(reset_state, client):
    couriers = [
        Courier(courier_id="cour_A", zone="centro", active_orders=0, max_capacity=3),
    ]

    order_data = {
        "order_id": "ord_inv",
        "timestamp": "2024-11-28T12:58:00Z",
        "pickup_zone": "centro",
        "distance_km": 1.0,
        "priority": "super_urgent",
        "couriers": [c.model_dump() for c in couriers],
    }
    resp = await client.post("/assign", json=order_data)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_no_couriers_provided(reset_state, client):
    order_data = {
        "order_id": "ord_nocourier",
        "timestamp": "2024-11-28T12:58:00Z",
        "pickup_zone": "centro",
        "distance_km": 1.0,
        "priority": "normal",
        "couriers": [],
    }
    resp = await client.post("/assign", json=order_data)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_never_exceeds_capacity(reset_state, client):
    couriers = [
        Courier(courier_id=f"cour_{i}", zone="centro", active_orders=0, max_capacity=2)
        for i in range(3)
    ]
    await client.post("/couriers/init", json=[c.model_dump() for c in couriers])

    for i in range(15):
        order = make_order(f"ord_cap_{i}", zone="centro")
        order.couriers = couriers
        await client.post("/assign", json=order.model_dump())

    final_couriers = await courier_state.get_couriers()
    for c in final_couriers:
        assert c.active_orders <= c.max_capacity, (
            f"Courier {c.courier_id} has {c.active_orders} > {c.max_capacity}"
        )


@pytest.mark.asyncio
async def test_contention_expiry_allows_orders_again(reset_state, client):
    from app.config import update_config
    update_config(containment_duration_seconds=2, containment_threshold=3)

    couriers = [
        Courier(courier_id="cour_Z", zone="centro", active_orders=1, max_capacity=1),
    ]
    await client.post("/couriers/init", json=[c.model_dump() for c in couriers])

    for i in range(3):
        order = make_order(f"ord_cont_{i}", zone="centro", priority="normal")
        order.couriers = couriers
        await client.post("/assign", json=order.model_dump())

    await asyncio.sleep(2.5)

    couriers2 = [
        Courier(courier_id="cour_Z", zone="centro", active_orders=0, max_capacity=1),
    ]
    await client.post("/couriers/init", json=[c.model_dump() for c in couriers2])

    order = make_order("ord_after", zone="centro", priority="normal")
    order.couriers = couriers2
    resp = await client.post("/assign", json=order.model_dump())
    result = resp.json()

    assert result["status"] != "REJECTED" or "surge_window_active" not in str(result["reasons"]), (
        "Order should not be rejected after contention expired"
    )
