from __future__ import annotations

from unittest.mock import patch, MagicMock


def test_status(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_ok(client):
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    with patch("src.api.v1.routes.health.get_db", return_value=mock_cur):
        with patch("src.api.v1.routes.health.cache_stats", return_value={"status": "ok"}):
            r = client.get("/api/v1/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["cache"] == "ok"
    assert "version" in body
    assert "uptime_seconds" in body


def test_health_db_error(client):
    def boom():
        raise RuntimeError("DB pool not initialized")

    with patch("src.api.v1.routes.health.get_db", side_effect=boom):
        with patch("src.api.v1.routes.health.cache_stats", return_value={"status": "unavailable"}):
            r = client.get("/api/v1/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert "error" in body["database"]


def test_health_cache_unavailable(client):
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    with patch("src.api.v1.routes.health.get_db", return_value=mock_cur):
        with patch("src.api.v1.routes.health.cache_stats", return_value={"status": "unavailable"}):
            r = client.get("/api/v1/health")

    assert r.status_code == 200
    assert r.json()["cache"] == "unavailable"
