"""
Background tasks via FastAPI BackgroundTasks.

Used for non-critical post-response work: cache warming, odometer updates,
audit logging. The response is returned to the caller immediately;
these run after the HTTP response is sent.

Known limitation: BackgroundTasks run in the same process/thread pool.
For heavy work (bulk exports, report generation), use Celery + Redis
as the broker. That's out of scope here but the architecture supports it —
same Redis instance, different queue.
"""

from __future__ import annotations

import json

from src.core.cache import cache_invalidate
from src.core.database import get_db
from src.core.logging import get_logger

logger = get_logger(__name__)


def update_vehicle_odometer(vehicle_id: int, new_odometer_km: int) -> None:
    """Update odometer and invalidate cached vehicle data."""
    try:
        with get_db() as cur:
            cur.execute(
                "UPDATE vehicles SET odometer_km = %s, last_seen_at = NOW() WHERE vehicle_id = %s",
                (new_odometer_km, vehicle_id),
            )
        count = cache_invalidate("vehicles")
        logger.info(json.dumps({
            "task": "update_odometer",
            "vehicle_id": vehicle_id,
            "new_odometer_km": new_odometer_km,
            "cache_keys_cleared": count,
        }))
    except Exception as exc:
        logger.error(json.dumps({"task": "update_odometer", "error": str(exc)}))


def log_query_audit(endpoint: str, params: dict, result_count: int, duration_ms: float) -> None:
    """Async audit log — fires after response is sent."""
    logger.info(json.dumps({
        "event": "query_audit",
        "endpoint": endpoint,
        "params": params,
        "result_count": result_count,
        "duration_ms": round(duration_ms, 2),
    }))


def warm_fault_code_cache() -> None:
    """Pre-warm the fault code summary cache after a bulk ingestion."""
    from src.core.cache import cache_set
    from src.repositories.diagnostics import get_fault_code_summary
    try:
        data = get_fault_code_summary(limit=50)
        cache_set("fault_codes", {"limit": 50}, data, ttl=3600)
        logger.info(json.dumps({"task": "warm_fault_cache", "entries": len(data)}))
    except Exception as exc:
        logger.error(json.dumps({"task": "warm_fault_cache", "error": str(exc)}))
