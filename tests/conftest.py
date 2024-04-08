from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

VEHICLE = {
    "vehicle_id": 1,
    "vin": "1HGCM82633A123456",
    "make": "Honda",
    "model": "Accord",
    "year": 2021,
    "fuel_type": "PETROL",
    "engine_displacement_cc": 1500,
    "transmission_type": "AUTOMATIC",
    "odometer_km": 42000,
    "last_seen_at": datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
    "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
}

EVENT = {
    "event_id": 101,
    "vehicle_id": 1,
    "vin": "1HGCM82633A123456",
    "event_type": "FAULT",
    "severity": "HIGH",
    "fault_code": "P0300",
    "fault_description": "Random misfire detected",
    "engine_temp_celsius": 95.5,
    "rpm": 2200,
    "vehicle_speed_kmh": 80.0,
    "battery_voltage": 12.4,
    "fuel_level_pct": 45.0,
    "recorded_at": datetime(2024, 3, 10, 8, 30, 0, tzinfo=timezone.utc),
}

FAULT_CODE = {
    "fault_code": "P0300",
    "fault_description": "Random misfire detected",
    "occurrence_count": 150,
    "affected_vehicles": 12,
    "first_seen": datetime(2023, 6, 1, tzinfo=timezone.utc),
    "last_seen": datetime(2024, 3, 10, tzinfo=timezone.utc),
}

STATS = {
    "total_events": 500000,
    "events_last_24h": 1200,
    "events_last_7d": 8400,
    "critical_events": 3100,
    "unique_vehicles": 980,
}


# ---------------------------------------------------------------------------
# Client fixture — patches infrastructure so no real Postgres/Redis needed
# ---------------------------------------------------------------------------

@pytest.fixture
def bypass_cache(monkeypatch):
    """Stub out Redis cache so route tests don't require a real Redis."""
    monkeypatch.setattr("src.core.cache.cache_get", lambda *a, **kw: None)
    monkeypatch.setattr("src.core.cache.cache_set", lambda *a, **kw: None)


@pytest.fixture
def client(bypass_cache):
    from src.api.main import app
    with (
        patch("src.api.main.init_db_pool"),
        patch("src.api.main.close_db_pool"),
        patch("src.api.main.init_cache"),
        patch("src.api.main.close_cache"),
    ):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
