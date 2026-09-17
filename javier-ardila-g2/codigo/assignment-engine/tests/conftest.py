import asyncio
import pytest
import pytest_asyncio

from app.models import Courier, Order
from app.state.courier_state import courier_state
from app.state.rate_limiter import rate_limiter
from app.state.wait_queue import wait_queue
from app.resilience.circuit_breaker import circuit_breaker


@pytest_asyncio.fixture
async def sample_couriers():
    return [
        Courier(courier_id="cour_A", zone="centro", active_orders=1, max_capacity=3),
        Courier(courier_id="cour_B", zone="norte", active_orders=0, max_capacity=3),
        Courier(courier_id="cour_C", zone="centro", active_orders=3, max_capacity=3),
    ]


@pytest_asyncio.fixture
async def sample_order():
    return Order(
        order_id="ord_00234",
        timestamp="2024-11-28T12:58:00Z",
        pickup_zone="centro",
        distance_km=3.2,
        priority="express",
    )


@pytest_asyncio.fixture
async def reset_state():
    await courier_state.reset_all()
    await rate_limiter.reset()
    await wait_queue.reset()
    await circuit_breaker.reset()
    yield
    await courier_state.reset_all()
    await rate_limiter.reset()
    await wait_queue.reset()
    await circuit_breaker.reset()
