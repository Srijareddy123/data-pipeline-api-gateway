from __future__ import annotations

from unittest.mock import patch

from tests.conftest import EVENT, FAULT_CODE, STATS


# ---------------------------------------------------------------------------
# List events
# ---------------------------------------------------------------------------

def test_list_events_empty(client):
    with patch("src.api.v1.routes.diagnostics.repo.list_diagnostic_events", return_value=([], 0)):
        r = client.get("/api/v1/diagnostics/events")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["total"] == 0


def test_list_events_returns_items(client):
    with patch("src.api.v1.routes.diagnostics.repo.list_diagnostic_events", return_value=([EVENT], 1)):
        r = client.get("/api/v1/diagnostics/events")
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["event_id"] == EVENT["event_id"]
    assert data[0]["fault_code"] == "P0300"


def test_list_events_filter_params_forwarded(client):
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return ([], 0)

    with patch("src.api.v1.routes.diagnostics.repo.list_diagnostic_events", side_effect=fake_list):
        client.get("/api/v1/diagnostics/events?vehicle_id=1&severity=HIGH&fault_code=P0300")

    assert captured["vehicle_id"] == 1
    assert captured["severity"] == "HIGH"
    assert captured["fault_code"] == "P0300"


def test_list_events_pagination(client):
    rows = [EVENT] * 50
    with patch("src.api.v1.routes.diagnostics.repo.list_diagnostic_events", return_value=(rows, 200)):
        r = client.get("/api/v1/diagnostics/events?page=1&page_size=50")
    body = r.json()
    assert body["total_pages"] == 4
    assert body["has_next"] is True


def test_list_events_invalid_sort_order(client):
    r = client.get("/api/v1/diagnostics/events?sort_order=sideways")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Get event by ID
# ---------------------------------------------------------------------------

def test_get_event_found(client):
    with patch("src.api.v1.routes.diagnostics.repo.get_event_by_id", return_value=EVENT):
        r = client.get("/api/v1/diagnostics/events/101")
    assert r.status_code == 200
    assert r.json()["event_id"] == 101


def test_get_event_not_found(client):
    with patch("src.api.v1.routes.diagnostics.repo.get_event_by_id", return_value=None):
        r = client.get("/api/v1/diagnostics/events/99999")
    assert r.status_code == 404
    assert "99999" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Fault codes
# ---------------------------------------------------------------------------

def test_fault_codes_returns_list(client):
    with patch("src.api.v1.routes.diagnostics.repo.get_fault_code_summary", return_value=[FAULT_CODE]):
        r = client.get("/api/v1/diagnostics/fault-codes")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data[0]["fault_code"] == "P0300"
    assert data[0]["occurrence_count"] == 150


def test_fault_codes_limit_param(client):
    from unittest.mock import MagicMock, call
    mock_fn = MagicMock(return_value=[FAULT_CODE])
    with patch("src.api.v1.routes.diagnostics.repo.get_fault_code_summary", mock_fn):
        client.get("/api/v1/diagnostics/fault-codes?limit=5")

    # First call is from the route handler (limit=5); second is the bg warm task (limit=50)
    assert mock_fn.call_args_list[0] == call(limit=5)


def test_fault_codes_limit_max(client):
    r = client.get("/api/v1/diagnostics/fault-codes?limit=999")
    assert r.status_code == 422


def test_fault_codes_empty(client):
    with patch("src.api.v1.routes.diagnostics.repo.get_fault_code_summary", return_value=[]):
        r = client.get("/api/v1/diagnostics/fault-codes")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_returns_counts(client):
    with patch("src.api.v1.routes.diagnostics.repo.get_diagnostic_stats", return_value=STATS):
        r = client.get("/api/v1/diagnostics/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_events"] == 500000
    assert body["critical_events"] == 3100
    assert body["unique_vehicles"] == 980
