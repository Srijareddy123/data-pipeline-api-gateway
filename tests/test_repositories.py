from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.repositories import vehicles as v_repo
from src.repositories import diagnostics as d_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

VEHICLE_ROW = {
    "vehicle_id": 1,
    "vin": "1HGCM82633A123456",
    "make": "Honda",
    "model": "Accord",
    "year": 2021,
    "fuel_type": "PETROL",
    "engine_displacement_cc": 1500,
    "transmission_type": "AUTOMATIC",
    "odometer_km": 42000,
    "last_seen_at": _NOW,
    "created_at": _NOW,
}

EVENT_ROW = {
    "event_id": 101,
    "vehicle_id": 1,
    "vin": "1HGCM82633A123456",
    "event_type": "FAULT",
    "severity": "HIGH",
    "fault_code": "P0300",
    "fault_description": "Misfire",
    "engine_temp_celsius": 95.5,
    "rpm": 2200,
    "vehicle_speed_kmh": 80.0,
    "battery_voltage": 12.4,
    "fuel_level_pct": 45.0,
    "recorded_at": _NOW,
}


_UNSET = object()


def _mock_cur(fetchone=_UNSET, fetchall=_UNSET):
    """Return a mock cursor that yields from get_db context manager."""
    cur = MagicMock()
    cur.fetchone.return_value = None if fetchone is _UNSET else fetchone
    cur.fetchall.return_value = [] if fetchall is _UNSET else fetchall

    @contextmanager
    def _get_db():
        yield cur

    return cur, _get_db


# ---------------------------------------------------------------------------
# Vehicle repository
# ---------------------------------------------------------------------------

class TestListVehicles:
    def test_returns_rows_and_total(self):
        cur, get_db = _mock_cur(
            fetchone={"total": 1},
            fetchall=[VEHICLE_ROW],
        )
        with patch("src.repositories.vehicles.get_db", get_db):
            rows, total = v_repo.list_vehicles(
                make=None, model=None, year_from=None, year_to=None,
                fuel_type=None, min_odometer_km=None, max_odometer_km=None,
                sort_by="vehicle_id", sort_order="desc", limit=50, offset=0,
            )
        assert total == 1
        assert len(rows) == 1
        assert rows[0]["vin"] == "1HGCM82633A123456"

    def test_empty_result(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        with patch("src.repositories.vehicles.get_db", get_db):
            rows, total = v_repo.list_vehicles(
                make=None, model=None, year_from=None, year_to=None,
                fuel_type=None, min_odometer_km=None, max_odometer_km=None,
                sort_by="vehicle_id", sort_order="asc", limit=50, offset=0,
            )
        assert total == 0
        assert rows == []

    def test_filters_build_where_clause(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        with patch("src.repositories.vehicles.get_db", get_db):
            v_repo.list_vehicles(
                make="Honda", model="Accord", year_from=2020, year_to=2024,
                fuel_type="PETROL", min_odometer_km=1000, max_odometer_km=50000,
                sort_by="make", sort_order="asc", limit=10, offset=0,
            )
        # Both COUNT and SELECT queries should have been executed
        assert cur.execute.call_count == 2

    def test_unknown_sort_column_falls_back(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        with patch("src.repositories.vehicles.get_db", get_db):
            v_repo.list_vehicles(
                make=None, model=None, year_from=None, year_to=None,
                fuel_type=None, min_odometer_km=None, max_odometer_km=None,
                sort_by="injected; DROP TABLE--",
                sort_order="asc", limit=10, offset=0,
            )
        # Should not raise; falls back to vehicle_id
        assert cur.execute.call_count == 2


class TestGetVehicleById:
    def test_found(self):
        _, get_db = _mock_cur(fetchone=VEHICLE_ROW)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_by_id(1)
        assert result is not None
        assert result["vehicle_id"] == 1

    def test_not_found(self):
        _, get_db = _mock_cur(fetchone=None)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_by_id(9999)
        assert result is None


class TestGetVehicleByVin:
    def test_found(self):
        _, get_db = _mock_cur(fetchone=VEHICLE_ROW)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_by_vin("1HGCM82633A123456")
        assert result["vin"] == "1HGCM82633A123456"

    def test_not_found(self):
        _, get_db = _mock_cur(fetchone=None)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_by_vin("UNKNOWN")
        assert result is None


class TestGetVehicleSummary:
    def test_found(self):
        summary_row = {
            "vehicle_id": 1, "vin": "1HGCM82633A123456",
            "make": "Honda", "model": "Accord", "year": 2021,
            "total_events": 42, "last_event_at": _NOW,
        }
        _, get_db = _mock_cur(fetchone=summary_row)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_summary(1)
        assert result["total_events"] == 42

    def test_not_found(self):
        _, get_db = _mock_cur(fetchone=None)
        with patch("src.repositories.vehicles.get_db", get_db):
            result = v_repo.get_vehicle_summary(9999)
        assert result is None


# ---------------------------------------------------------------------------
# Diagnostic repository
# ---------------------------------------------------------------------------

class TestListDiagnosticEvents:
    def test_returns_rows_and_total(self):
        cur, get_db = _mock_cur(fetchone={"total": 1}, fetchall=[EVENT_ROW])
        with patch("src.repositories.diagnostics.get_db", get_db):
            rows, total = d_repo.list_diagnostic_events(
                vehicle_id=1, vin=None, event_type=None, severity=None,
                fault_code=None, date_from=None, date_to=None,
                min_engine_temp=None, max_engine_temp=None,
                sort_by="recorded_at", sort_order="desc", limit=50, offset=0,
            )
        assert total == 1
        assert rows[0]["event_id"] == 101

    def test_all_filters(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        date_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2024, 3, 31, tzinfo=timezone.utc)
        with patch("src.repositories.diagnostics.get_db", get_db):
            rows, total = d_repo.list_diagnostic_events(
                vehicle_id=1, vin="1HGCM82633A123456",
                event_type="FAULT", severity="HIGH",
                fault_code="P0300", date_from=date_from, date_to=date_to,
                min_engine_temp=80.0, max_engine_temp=110.0,
                sort_by="severity", sort_order="asc", limit=10, offset=0,
            )
        assert total == 0
        assert cur.execute.call_count == 2

    def test_empty_filters(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        with patch("src.repositories.diagnostics.get_db", get_db):
            rows, total = d_repo.list_diagnostic_events(
                vehicle_id=None, vin=None, event_type=None, severity=None,
                fault_code=None, date_from=None, date_to=None,
                min_engine_temp=None, max_engine_temp=None,
                sort_by="recorded_at", sort_order="desc", limit=50, offset=0,
            )
        assert total == 0

    def test_unknown_sort_column_falls_back(self):
        cur, get_db = _mock_cur(fetchone={"total": 0}, fetchall=[])
        with patch("src.repositories.diagnostics.get_db", get_db):
            d_repo.list_diagnostic_events(
                vehicle_id=None, vin=None, event_type=None, severity=None,
                fault_code=None, date_from=None, date_to=None,
                min_engine_temp=None, max_engine_temp=None,
                sort_by="DROPDROP--", sort_order="desc", limit=10, offset=0,
            )
        # Didn't raise
        assert cur.execute.call_count == 2


class TestGetEventById:
    def test_found(self):
        _, get_db = _mock_cur(fetchone=EVENT_ROW)
        with patch("src.repositories.diagnostics.get_db", get_db):
            result = d_repo.get_event_by_id(101)
        assert result["event_id"] == 101

    def test_not_found(self):
        _, get_db = _mock_cur(fetchone=None)
        with patch("src.repositories.diagnostics.get_db", get_db):
            result = d_repo.get_event_by_id(9999)
        assert result is None


class TestGetFaultCodeSummary:
    def test_returns_list(self):
        fault_row = {
            "fault_code": "P0300", "fault_description": "Misfire",
            "occurrence_count": 10, "affected_vehicles": 3,
            "first_seen": _NOW, "last_seen": _NOW,
        }
        _, get_db = _mock_cur(fetchall=[fault_row])
        with patch("src.repositories.diagnostics.get_db", get_db):
            result = d_repo.get_fault_code_summary(limit=10)
        assert len(result) == 1
        assert result[0]["fault_code"] == "P0300"

    def test_empty(self):
        _, get_db = _mock_cur(fetchall=[])
        with patch("src.repositories.diagnostics.get_db", get_db):
            result = d_repo.get_fault_code_summary(limit=5)
        assert result == []


class TestGetDiagnosticStats:
    def test_returns_stats(self):
        stats_row = {
            "total_events": 500000,
            "events_last_24h": 1200,
            "events_last_7d": 8400,
            "critical_events": 3100,
            "unique_vehicles": 980,
        }
        _, get_db = _mock_cur(fetchone=stats_row)
        with patch("src.repositories.diagnostics.get_db", get_db):
            result = d_repo.get_diagnostic_stats()
        assert result["total_events"] == 500000
        assert result["unique_vehicles"] == 980
