import pytest
import pytest_asyncio
import asyncio

from app.models import Courier, Order, AssignmentResult, Reason
from app.resilience.circuit_breaker import CircuitBreaker, CircuitState
from app.engine.optimizer import optimizer
from app.state.courier_state import courier_state


@pytest.mark.asyncio
async def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)
    state = await cb.get_state()
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)

    async def failing_func():
        raise Exception("fail")

    for _ in range(3):
        result, state = await cb.call(failing_func)

    assert await cb.get_state() == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_recovers_to_half_open():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    async def failing_func():
        raise Exception("fail")

    for _ in range(3):
        await cb.call(failing_func)

    assert await cb.get_state() == CircuitState.OPEN

    await asyncio.sleep(1.1)

    state = await cb.get_state()
    assert state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_closes_on_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    async def failing_func():
        raise Exception("fail")

    async def success_func():
        return 42

    for _ in range(3):
        await cb.call(failing_func)

    await asyncio.sleep(1.1)

    result, state = await cb.call(success_func)
    assert result == 42
    assert await cb.get_state() == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_returns_none_when_open():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

    async def failing_func():
        raise Exception("fail")

    async def success_func():
        return 42

    for _ in range(3):
        await cb.call(failing_func)

    result, state = await cb.call(success_func)
    assert result is None


@pytest.mark.asyncio
async def test_optimizer_fallback_price(reset_state, sample_order, sample_couriers):
    await courier_state.init_couriers(sample_couriers)

    result = AssignmentResult(
        order_id=sample_order.order_id,
        status="ASSIGNED",
        assigned_courier="cour_A",
        reasons=[],
    )

    enriched = await optimizer.enrich_result(result, sample_order)

    assert enriched.cost is not None
    assert enriched.cost > 0
    assert enriched.pricing_status is not None
