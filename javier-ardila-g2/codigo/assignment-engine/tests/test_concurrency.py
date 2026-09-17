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


@pytest.mark.asyncio
async def test_concurrent_assignments_no_overassign(reset_state, client):
    couriers = [
        Courier(courier_id="cour_A", zone="centro", active_orders=0, max_capacity=2),
    ]

    orders = []
    for i in range(10):
        orders.append(
            Order(
                order_id=f"ord_conc_{i}",
                timestamp="2024-11-28T12:58:00Z",
                pickup_zone="centro",
                distance_km=1.0,
                priority="normal",
                couriers=couriers,
            )
        )

    tasks = [client.post("/assign", json=o.model_dump()) for o in orders]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for r in responses:
        if isinstance(r, Exception):
            continue
        if r.status_code == 200:
            results.append(r.json())

    assigned = [r for r in results if r["status"] == "ASSIGNED" and r["assigned_courier"] == "cour_A"]

    assert len(assigned) <= 2, f"Over-assigned! {len(assigned)} orders to cour_A (max_capacity=2)"


@pytest.mark.asyncio
async def test_concurrent_assignments_different_couriers(reset_state, client):
    couriers = [
        Courier(courier_id=f"cour_{i}", zone="centro", active_orders=0, max_capacity=1)
        for i in range(5)
    ]

    orders = []
    for i in range(10):
        orders.append(
            Order(
                order_id=f"ord_diff_{i}",
                timestamp="2024-11-28T12:58:00Z",
                pickup_zone="centro",
                distance_km=1.0,
                priority="normal",
                couriers=couriers,
            )
        )

    tasks = [client.post("/assign", json=o.model_dump()) for o in orders]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    assigned_couriers = []
    for r in responses:
        if isinstance(r, Exception):
            continue
        if r.status_code == 200:
            data = r.json()
            if data["status"] == "ASSIGNED":
                assigned_couriers.append(data["assigned_courier"])

    from collections import Counter
    counts = Counter(assigned_couriers)
    for courier_id, count in counts.items():
        assert count <= 1, f"Courier {courier_id} was assigned {count} times (max_capacity=1)"


@pytest.mark.asyncio
async def test_concurrent_state_consistency(reset_state, client):
    couriers = [
        Courier(courier_id="cour_X", zone="centro", active_orders=0, max_capacity=3),
        Courier(courier_id="cour_Y", zone="centro", active_orders=0, max_capacity=3),
    ]

    orders = []
    for i in range(20):
        orders.append(
            Order(
                order_id=f"ord_cons_{i}",
                timestamp="2024-11-28T12:58:00Z",
                pickup_zone="centro",
                distance_km=1.0,
                priority="normal",
                couriers=couriers,
            )
        )

    tasks = [client.post("/assign", json=o.model_dump()) for o in orders]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    assigned_count = 0
    for r in responses:
        if isinstance(r, Exception):
            continue
        if r.status_code == 200 and r.json()["status"] == "ASSIGNED":
            assigned_count += 1

    final_couriers = await courier_state.get_couriers()
    total_active = sum(c.active_orders for c in final_couriers)

    assert total_active <= 6, f"Total active orders {total_active} exceeds total capacity 6"
