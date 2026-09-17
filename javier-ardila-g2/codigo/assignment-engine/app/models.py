from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    NORMAL = "normal"
    EXPRESS = "express"


class OrderStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    QUEUED = "QUEUED"
    REJECTED = "REJECTED"


class PricingStatus(str, Enum):
    CIRCUIT_CLOSED = "circuit_closed"
    CIRCUIT_OPEN_DEGRADED = "circuit_open_degraded_flat_rate"
    CIRCUIT_HALF_OPEN = "circuit_half_open"
    PRICING_SUCCESS = "pricing_success"
    PRICING_FAILED = "pricing_failed"


class Courier(BaseModel):
    courier_id: str
    zone: str
    active_orders: int = 0
    max_capacity: int = 3


class Order(BaseModel):
    order_id: str
    timestamp: str
    pickup_zone: str
    distance_km: float = Field(ge=0)
    priority: Priority = Priority.NORMAL
    couriers: list[Courier] = []


class Reason(BaseModel):
    rule: str
    detail: str


class AssignmentResult(BaseModel):
    order_id: str
    status: str
    assigned_courier: Optional[str] = None
    reasons: list[Reason] = []
    cost: Optional[int] = None
    pricing_status: Optional[str] = None


class BatchOrderRequest(BaseModel):
    orders: list[Order]
    couriers: list[Courier]


class BatchAssignmentResult(BaseModel):
    results: list[AssignmentResult]
    total_cost: int
    strategy: str
