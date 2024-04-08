"""
PostgreSQL connection pool via psycopg2.

Deliberately raw psycopg2, no ORM. This project exists to understand the
full database-to-API path. An ORM would hide the partition pruning and
index behavior that's the whole point of building this.

In production (AWS RDS): change POSTGRES_HOST env var. Pool config stays identical.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_pool: pool.ThreadedConnectionPool | None = None


def init_db_pool() -> None:
    global _pool
    s = get_settings()
    _pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=s.db_pool_size,
        host=s.postgres_host,
        port=s.postgres_port,
        dbname=s.postgres_db,
        user=s.postgres_user,
        password=s.postgres_password,
        connect_timeout=10,
        options="-c statement_timeout=30000",  # 30s hard limit per query
    )
    logger.info(json.dumps({"message": "DB pool initialized", "pool_size": s.db_pool_size}))


def close_db_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_db() -> Generator[psycopg2.extensions.cursor, None, None]:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


class QueryTimer:
    def __init__(self, name: str):
        self.name = name
        self.duration_ms: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.perf_counter() - self._start) * 1000
        logger.debug(json.dumps({"query": self.name, "duration_ms": round(self.duration_ms, 2)}))
