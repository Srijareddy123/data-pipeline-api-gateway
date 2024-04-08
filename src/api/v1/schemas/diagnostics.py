from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DiagnosticEventResponse(BaseModel):
    event_id: int
    vehicle_id: int
    vin: str
    event_type: str
    severity: str
    fault_code: Optional[str] = None
    fault_description: Optional[str] = None
    engine_temp_celsius: Optional[float] = None
    rpm: Optional[int] = None
    vehicle_speed_kmh: Optional[float] = None
    battery_voltage: Optional[float] = None
    fuel_level_pct: Optional[float] = None
    recorded_at: datetime


class DiagnosticFilterParams(BaseModel):
    vehicle_id: Optional[int] = None
    vin: Optional[str] = None
    event_type: Optional[str] = None
    severity: Optional[str] = None
    fault_code: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_engine_temp: Optional[float] = None
    max_engine_temp: Optional[float] = None


class FaultCodeSummary(BaseModel):
    fault_code: str
    fault_description: Optional[str] = None
    occurrence_count: int
    affected_vehicles: int
    first_seen: datetime
    last_seen: datetime


class DiagnosticStats(BaseModel):
    total_events: int
    events_last_24h: int
    events_last_7d: int
    critical_events: int
    unique_vehicles: int
