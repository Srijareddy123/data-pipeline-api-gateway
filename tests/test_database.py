from __future__ import annotations

import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call

import pytest

import src.core.database as db_mod
from src.core.database import QueryTimer


@pytest.fixture(autouse=True)
def reset_pool():
    original = db_mod._pool
    yield
    db_mod._pool = original


# ---------------------------------------------------------------------------
# QueryTimer
# ---------------------------------------------------------------------------

def test_query_timer_records_duration():
    with QueryTimer("test_query") as t:
        time.sleep(0.01)
    assert t.duration_ms >= 10
    assert t.duration_ms < 500


def test_query_timer_name():
    with QueryTimer("my_query") as t:
        pass
    assert t.name == "my_query"


def test_query_timer_initial_duration_zero():
    t = QueryTimer("q")
    assert t.duration_ms == 0.0


# ---------------------------------------------------------------------------
# Pool init / close
# ---------------------------------------------------------------------------

def test_init_db_pool_creates_pool():
    mock_pool = MagicMock()
    with patch("src.core.database.pool.ThreadedConnectionPool", return_value=mock_pool) as mock_cls:
        with patch("src.core.database.get_settings") as mock_settings:
            mock_settings.return_value.postgres_host = "localhost"
            mock_settings.return_value.postgres_port = 5432
            mock_settings.return_value.postgres_db = "test_db"
            mock_settings.return_value.postgres_user = "user"
            mock_settings.return_value.postgres_password = "pass"
            mock_settings.return_value.db_pool_size = 5
            db_mod.init_db_pool()

    assert db_mod._pool is mock_pool
    mock_cls.assert_called_once()


def test_close_db_pool_calls_closeall():
    mock_pool = MagicMock()
    db_mod._pool = mock_pool
    db_mod.close_db_pool()
    mock_pool.closeall.assert_called_once()
    assert db_mod._pool is None


def test_close_db_pool_noop_when_none():
    db_mod._pool = None
    db_mod.close_db_pool()  # should not raise


# ---------------------------------------------------------------------------
# get_db context manager
# ---------------------------------------------------------------------------

def test_get_db_raises_when_pool_not_initialized():
    db_mod._pool = None
    with pytest.raises(RuntimeError, match="DB pool not initialized"):
        with db_mod.get_db():
            pass


def test_get_db_yields_cursor_and_commits():
    mock_conn = MagicMock()
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__ = lambda s: MagicMock()
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    db_mod._pool = mock_pool

    with db_mod.get_db():
        pass

    mock_conn.commit.assert_called_once()
    mock_pool.putconn.assert_called_once_with(mock_conn)


def test_get_db_rolls_back_on_exception():
    mock_conn = MagicMock()
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    db_mod._pool = mock_pool

    with pytest.raises(ValueError):
        with db_mod.get_db():
            raise ValueError("boom")

    mock_conn.rollback.assert_called_once()
    mock_pool.putconn.assert_called_once_with(mock_conn)
