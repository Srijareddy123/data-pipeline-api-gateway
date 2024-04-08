import time
from fastapi import APIRouter
from src.api.v1.schemas.common import HealthStatus
from src.core.cache import cache_stats
from src.core.database import get_db
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

_start_time = time.time()


@router.get("/health", response_model=HealthStatus, tags=["Health"])
def health_check():
    db_status = "ok"
    try:
        with get_db() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:
        db_status = f"error: {exc}"

    stats = cache_stats()
    cache_status = stats.get("status", "unavailable")

    return HealthStatus(
        status="ok" if db_status == "ok" else "degraded",
        version="1.0.0",
        database=db_status,
        cache=cache_status,
        uptime_seconds=round(time.time() - _start_time, 1),
        cache_stats=stats,
    )


@router.get("/status", tags=["Health"])
def status():
    return {"status": "ok", "service": "data-pipeline-api-gateway"}
