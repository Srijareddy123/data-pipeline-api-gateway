"""
Redis caching layer — local Docker, AWS ElastiCache in production.

Why Redis over Postgres materialized views or in-process dict:
- Materialized views need manual REFRESH; Redis expires automatically via TTL
- In-process cache doesn't survive restarts or multi-instance ECS deployments
- Redis gives one shared cache for all API instances behind the ALB

If Redis is down, requests fall through to Postgres. Deliberate choice:
availability > strict caching. A cache outage shouldn't take down the API.

Key convention: gateway:<resource>:<md5_of_params>
TTL: 5min for list queries, 1hr for reference/lookup data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_client: redis.Redis | None = None


def init_cache() -> None:
    global _client
    s = get_settings()
    _client = redis.Redis(
        host=s.redis_host,
        port=s.redis_port,
        password=s.redis_password or None,
        db=s.redis_db,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
        _client.ping()
        logger.info(json.dumps({"message": "Redis connected", "host": s.redis_host}))
    except redis.ConnectionError as exc:
        logger.warning(json.dumps({"message": "Redis unavailable, caching disabled", "error": str(exc)}))
        _client = None


def close_cache() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def _available() -> bool:
    return _client is not None


def _key(prefix: str, params: dict) -> str:
    h = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    return f"gateway:{prefix}:{h}"


def cache_get(prefix: str, params: dict) -> Any | None:
    if not _available():
        return None
    k = _key(prefix, params)
    try:
        raw = _client.get(k)  # type: ignore[union-attr]
        if raw:
            logger.debug(json.dumps({"event": "cache_hit", "key": k}))
            return json.loads(raw)
        return None
    except Exception as exc:
        logger.warning(json.dumps({"event": "cache_error", "op": "get", "error": str(exc)}))
        return None


def cache_set(prefix: str, params: dict, value: Any, ttl: int | None = None) -> None:
    if not _available():
        return
    s = get_settings()
    k = _key(prefix, params)
    try:
        _client.setex(k, ttl or s.cache_ttl_seconds, json.dumps(value, default=str))  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning(json.dumps({"event": "cache_error", "op": "set", "error": str(exc)}))


def cache_invalidate(prefix: str) -> int:
    if not _available():
        return 0
    try:
        keys = list(_client.scan_iter(f"gateway:{prefix}:*"))  # type: ignore[union-attr]
        return _client.delete(*keys) if keys else 0  # type: ignore[union-attr]
    except Exception:
        return 0


def cache_stats() -> dict:
    if not _available():
        return {"status": "unavailable"}
    try:
        info = _client.info()  # type: ignore[union-attr]
        return {
            "status": "ok",
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }
    except Exception:
        return {"status": "error"}
