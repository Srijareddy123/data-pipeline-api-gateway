from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from src.api.v1.schemas.common import PaginationParams, PaginatedResponse
from src.api.v1.schemas.vehicles import VehicleResponse, VehicleFilterParams, VehicleSummary
from src.core.cache import cache_get, cache_set
from src.core.config import get_settings
from src.core.rate_limit import check_rate_limit, RateLimitExceeded
from src.repositories import vehicles as repo
from src.tasks.background import log_query_audit

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def _rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    try:
        check_rate_limit(identifier=f"ip:{client_ip}")
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Retry after {exc.retry_after}s.")


@router.get("", response_model=PaginatedResponse[VehicleResponse])
def list_vehicles(
    request: Request,
    background_tasks: BackgroundTasks,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    sort_by: str = Query(default="vehicle_id"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    year_from: int | None = Query(default=None, ge=1990, le=2030),
    year_to: int | None = Query(default=None, ge=1990, le=2030),
    fuel_type: str | None = Query(default=None),
    min_odometer_km: int | None = Query(default=None, ge=0),
    max_odometer_km: int | None = Query(default=None, ge=0),
    _rl: None = Depends(_rate_limit),
):
    settings = get_settings()
    params = dict(
        make=make, model=model, year_from=year_from, year_to=year_to,
        fuel_type=fuel_type, min_odometer_km=min_odometer_km,
        max_odometer_km=max_odometer_km, sort_by=sort_by,
        sort_order=sort_order, page=page, page_size=page_size,
    )
    cached = cache_get("vehicles", params)
    if cached:
        return cached

    start = time.perf_counter()
    offset = (page - 1) * page_size
    rows, total = repo.list_vehicles(
        make=make, model=model, year_from=year_from, year_to=year_to,
        fuel_type=fuel_type, min_odometer_km=min_odometer_km,
        max_odometer_km=max_odometer_km, sort_by=sort_by, sort_order=sort_order,
        limit=page_size, offset=offset,
    )
    duration = (time.perf_counter() - start) * 1000
    result = PaginatedResponse.build(
        data=rows, total=total, page=page, page_size=page_size
    ).model_dump()
    cache_set("vehicles", params, result)
    background_tasks.add_task(log_query_audit, "/vehicles", params, len(rows), duration)
    return result


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: int, request: Request, _rl: None = Depends(_rate_limit)):
    cached = cache_get("vehicle_id", {"id": vehicle_id})
    if cached:
        return cached

    row = repo.get_vehicle_by_id(vehicle_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

    cache_set("vehicle_id", {"id": vehicle_id}, row, ttl=get_settings().cache_ttl_long_seconds)
    return row


@router.get("/vin/{vin}", response_model=VehicleResponse)
def get_vehicle_by_vin(vin: str, request: Request, _rl: None = Depends(_rate_limit)):
    cached = cache_get("vehicle_vin", {"vin": vin})
    if cached:
        return cached

    row = repo.get_vehicle_by_vin(vin.upper())
    if not row:
        raise HTTPException(status_code=404, detail=f"VIN {vin} not found")

    cache_set("vehicle_vin", {"vin": vin}, row, ttl=get_settings().cache_ttl_long_seconds)
    return row


@router.get("/{vehicle_id}/summary", response_model=VehicleSummary)
def get_vehicle_summary(vehicle_id: int, request: Request, _rl: None = Depends(_rate_limit)):
    cached = cache_get("vehicle_summary", {"id": vehicle_id})
    if cached:
        return cached

    row = repo.get_vehicle_summary(vehicle_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

    cache_set("vehicle_summary", {"id": vehicle_id}, row)
    return row
