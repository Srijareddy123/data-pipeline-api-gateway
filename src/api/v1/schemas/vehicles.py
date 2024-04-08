from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class VehicleResponse(BaseModel):
    vehicle_id: int
    vin: str
    make: str
    model: str
    year: int
    fuel_type: str
    engine_displacement_cc: Optional[int] = None
    transmission_type: Optional[str] = None
    odometer_km: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime


class VehicleFilterParams(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year_from: Optional[int] = Field(default=None, ge=1990, le=2030)
    year_to: Optional[int] = Field(default=None, ge=1990, le=2030)
    fuel_type: Optional[str] = None
    min_odometer_km: Optional[int] = Field(default=None, ge=0)
    max_odometer_km: Optional[int] = Field(default=None, ge=0)

    @field_validator("year_to")
    @classmethod
    def validate_year_range(cls, v, info):
        if v is not None and info.data.get("year_from") and v < info.data["year_from"]:
            raise ValueError("year_to must be >= year_from")
        return v


class VehicleSummary(BaseModel):
    vehicle_id: int
    vin: str
    make: str
    model: str
    year: int
    total_events: int
    last_event_at: Optional[datetime] = None
