from __future__ import annotations

from pydantic import BaseModel

from app.models import Courier


class RuleConfig(BaseModel):
    same_zone_preferred: bool = True
    capacity_check: bool = True
    least_loaded: bool = True

    rate_limit_enabled: bool = True
    max_orders_per_window: int = 3
    rate_window_seconds: int = 10

    zone_balancing_enabled: bool = True
    zone_overflow_threshold: int = 4

    containment_enabled: bool = True
    containment_threshold: int = 3
    containment_duration_seconds: int = 120

    cost_optimization_enabled: bool = True
    base_rate_cop: int = 3000
    per_km_rate_cop: int = 1000

    circuit_failure_threshold: int = 3
    circuit_open_duration_seconds: int = 15

    pricing_service_url: str = "http://localhost:8001"
    pricing_failure_rate: float = 0.3

    zone_neighbors: dict[str, list[str]] = {
        "centro": ["norte", "sur", "occidente", "oriente"],
        "norte": ["centro", "occidente", "oriente"],
        "sur": ["centro", "occidente", "oriente"],
        "occidente": ["centro", "norte", "sur"],
        "oriente": ["centro", "norte", "sur"],
    }


_config: RuleConfig = RuleConfig()


def get_config() -> RuleConfig:
    return _config


def update_config(**kwargs) -> RuleConfig:
    global _config
    data = _config.model_dump()
    data.update(kwargs)
    _config = RuleConfig(**data)
    return _config
