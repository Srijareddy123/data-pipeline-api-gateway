from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from src.api.v1.schemas.common import PaginatedResponse
from src.api.v1.schemas.diagnostics import (
    DiagnosticEventResponse, FaultCodeSummary, DiagnosticStats,
)
from src.core.cache import cache_get, cache_set
from src.core.config import get_settings
from src.core.rate_limit import check_rate_limit, RateLimitExceeded
from src.repositories import diagnostics as repo
from src.tasks.background import log_query_audit, warm_fault_code_cache

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


def _rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    try:
        check_rate_limit(identifier=f"ip:{client_ip}")
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Retry after {exc.retry_after}s.")


@router.get("/events", response_model=PaginatedResponse[DiagnosticEventResponse])
def list_events(
    request: Request,
    background_tasks: BackgroundTasks,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    sort_by: str = Query(default="recorded_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    vehicle_id: int | None = Query(default=None),
    vin: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    fault_code: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_engine_temp: float | None = Query(default=None),
    max_engine_temp: float | None = Query(default=None),
    _rl: None = Depends(_rate_limit),
):
    params = dict(
        vehicle_id=vehicle_id, vin=vin, event_type=event_type, severity=severity,
        fault_code=fault_code, date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        min_engine_temp=min_engine_temp, max_engine_temp=max_engine_temp,
        sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size,
    )
    cached = cache_get("events", params)
    if cached:
        return cached

    start = time.perf_counter()
    offset = (page - 1) * page_size
    rows, total = repo.list_diagnostic_events(
        vehicle_id=vehicle_id, vin=vin, event_type=event_type, severity=severity,
        fault_code=fault_code, date_from=date_from, date_to=date_to,
        min_engine_temp=min_engine_temp, max_engine_temp=max_engine_temp,
        sort_by=sort_by, sort_order=sort_order, limit=page_size, offset=offset,
    )
    duration = (time.perf_counter() - start) * 1000
    result = PaginatedResponse.build(data=rows, total=total, page=page, page_size=page_size).model_dump()
    cache_set("events", params, result)
    background_tasks.add_task(log_query_audit, "/diagnostics/events", params, len(rows), duration)
    return result


@router.get("/events/{event_id}", response_model=DiagnosticEventResponse)
def get_event(event_id: int, request: Request, _rl: None = Depends(_rate_limit)):
    cached = cache_get("event_id", {"id": event_id})
    if cached:
        return cached

    row = repo.get_event_by_id(event_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    cache_set("event_id", {"id": event_id}, row, ttl=get_settings().cache_ttl_long_seconds)
    return row


@router.get("/fault-codes", response_model=list[FaultCodeSummary])
def get_fault_codes(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(default=20, ge=1, le=100),
    _rl: None = Depends(_rate_limit),
):
    params = {"limit": limit}
    cached = cache_get("fault_codes", params)
    if cached:
        return cached

    rows = repo.get_fault_code_summary(limit=limit)
    cache_set("fault_codes", params, rows, ttl=get_settings().cache_ttl_long_seconds)
    background_tasks.add_task(warm_fault_code_cache)
    return rows


@router.get("/stats", response_model=DiagnosticStats)
def get_stats(request: Request, _rl: None = Depends(_rate_limit)):
    cached = cache_get("stats", {})
    if cached:
        return cached

    stats = repo.get_diagnostic_stats()
    cache_set("stats", {}, stats, ttl=60)
    return stats
