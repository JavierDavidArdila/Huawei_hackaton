from __future__ import annotations

import random
import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Pricing Service (Mock)",
    description="Servicio externo simulado de cálculo de tarifa dinámica",
    version="1.0.0",
)


class PriceRequest(BaseModel):
    order_id: str
    distance_km: float
    priority: str = "normal"


class PriceResponse(BaseModel):
    order_id: str
    price: int
    strategy: str


FAILURE_RATE = 0.30
BASE_RATE_COP = 3000
PER_KM_RATE_COP = 1000
EXPRESS_MULTIPLIER = 1.5


@app.post("/price", response_model=PriceResponse)
async def calculate_price(req: PriceRequest):
    if random.random() < FAILURE_RATE:
        if random.random() < 0.5:
            await asyncio.sleep(3.0)
            raise HTTPException(status_code=504, detail="Pricing service timeout")
        else:
            raise HTTPException(status_code=500, detail="Pricing service error")

    base = BASE_RATE_COP + (req.distance_km * PER_KM_RATE_COP)
    if req.priority == "express":
        base *= EXPRESS_MULTIPLIER

    surge = random.uniform(0.9, 1.3)
    price = int(base * surge)

    return PriceResponse(
        order_id=req.order_id,
        price=price,
        strategy="dynamic_surge",
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "failure_rate": FAILURE_RATE}


@app.get("/")
async def root():
    return {"service": "Pricing Service (Mock)", "failure_rate": FAILURE_RATE}
