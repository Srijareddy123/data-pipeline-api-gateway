from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import VEHICLE


def _paginated(rows, total=None):
    total = total if total is not None else len(rows)
    return (rows, total)


# ---------------------------------------------------------------------------
# List vehicles
# ---------------------------------------------------------------------------

def test_list_vehicles_empty(client):
    with patch("src.api.v1.routes.vehicles.repo.list_vehicles", return_value=([], 0)):
        r = client.get("/api/v1/vehicles")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 1
    assert body["has_next"] is False
    assert body["has_prev"] is False


def test_list_vehicles_returns_items(client):
    with patch("src.api.v1.routes.vehicles.repo.list_vehicles", return_value=([VEHICLE], 1)):
        r = client.get("/api/v1/vehicles")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["vin"] == VEHICLE["vin"]
    assert data[0]["make"] == "Honda"


def test_list_vehicles_pagination_headers(client):
    rows = [VEHICLE] * 50
    with patch("src.api.v1.routes.vehicles.repo.list_vehicles", return_value=(rows, 150)):
        r = client.get("/api/v1/vehicles?page=1&page_size=50")
    body = r.json()
    assert body["total"] == 150
    assert body["total_pages"] == 3
    assert body["has_next"] is True
    assert body["has_prev"] is False


def test_list_vehicles_page_two(client):
    rows = [VEHICLE] * 50
    with patch("src.api.v1.routes.vehicles.repo.list_vehicles", return_value=(rows, 150)):
        r = client.get("/api/v1/vehicles?page=2&page_size=50")
    body = r.json()
    assert body["has_prev"] is True
    assert body["has_next"] is True


def test_list_vehicles_filter_params_forwarded(client):
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return ([VEHICLE], 1)

    with patch("src.api.v1.routes.vehicles.repo.list_vehicles", side_effect=fake_list):
        client.get("/api/v1/vehicles?make=Honda&year_from=2020&fuel_type=PETROL")

    assert captured["make"] == "Honda"
    assert captured["year_from"] == 2020
    assert captured["fuel_type"] == "PETROL"


def test_list_vehicles_invalid_sort_order(client):
    r = client.get("/api/v1/vehicles?sort_order=random")
    assert r.status_code == 422


def test_list_vehicles_page_size_exceeds_max(client):
    r = client.get("/api/v1/vehicles?page_size=9999")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Get vehicle by ID
# ---------------------------------------------------------------------------

def test_get_vehicle_found(client):
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_by_id", return_value=VEHICLE):
        r = client.get("/api/v1/vehicles/1")
    assert r.status_code == 200
    assert r.json()["vehicle_id"] == 1


def test_get_vehicle_not_found(client):
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_by_id", return_value=None):
        r = client.get("/api/v1/vehicles/9999")
    assert r.status_code == 404
    assert "9999" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Get vehicle by VIN
# ---------------------------------------------------------------------------

def test_get_vehicle_by_vin_found(client):
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_by_vin", return_value=VEHICLE):
        r = client.get("/api/v1/vehicles/vin/1HGCM82633A123456")
    assert r.status_code == 200
    assert r.json()["vin"] == "1HGCM82633A123456"


def test_get_vehicle_by_vin_uppercases(client):
    captured = {}

    def fake_get(vin):
        captured["vin"] = vin
        return VEHICLE

    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_by_vin", side_effect=fake_get):
        client.get("/api/v1/vehicles/vin/1hgcm82633a123456")

    assert captured["vin"] == "1HGCM82633A123456"


def test_get_vehicle_by_vin_not_found(client):
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_by_vin", return_value=None):
        r = client.get("/api/v1/vehicles/vin/UNKNOWNVIN")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Vehicle summary
# ---------------------------------------------------------------------------

def test_get_vehicle_summary_found(client):
    summary = {
        "vehicle_id": 1,
        "vin": "1HGCM82633A123456",
        "make": "Honda",
        "model": "Accord",
        "year": 2021,
        "total_events": 42,
        "last_event_at": None,
    }
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_summary", return_value=summary):
        r = client.get("/api/v1/vehicles/1/summary")
    assert r.status_code == 200
    assert r.json()["total_events"] == 42


def test_get_vehicle_summary_not_found(client):
    with patch("src.api.v1.routes.vehicles.repo.get_vehicle_summary", return_value=None):
        r = client.get("/api/v1/vehicles/9999/summary")
    assert r.status_code == 404
