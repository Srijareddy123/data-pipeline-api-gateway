"""
FastAPI application entry point.

Local: uvicorn src.api.main:app --reload --port 8000
Docker: docker compose up

API docs: http://localhost:8000/docs
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.routes import health, vehicles, diagnostics
from src.core.cache import init_cache, close_cache
from src.core.config import get_settings
from src.core.database import init_db_pool, close_db_pool
from src.core.logging import get_logger
from src.core.rate_limit import set_rate_limit_client

logger = get_logger(__name__)

_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db_pool()
    init_cache()

    # Wire up the rate limiter to the same Redis client
    try:
        rl_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        rl_client.ping()
        set_rate_limit_client(rl_client)
    except Exception:
        pass  # Rate limiting degrades gracefully without Redis

    logger.info('{"message": "Startup complete"}')
    yield
    close_cache()
    close_db_pool()
    logger.info('{"message": "Shutdown complete"}')


app = FastAPI(
    title="Data Pipeline API Gateway",
    description=(
        "Production-grade REST API exposing vehicle diagnostic pipeline data. "
        "PostgreSQL with table partitioning, Redis caching, rate limiting, "
        "and full pagination/filtering on all endpoints."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f'{{"error": "{type(exc).__name__}", "detail": "{exc}", "path": "{request.url.path}"}}')
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# Mount v1 routes
app.include_router(health.router, prefix="/api/v1")
app.include_router(vehicles.router, prefix="/api/v1")
app.include_router(diagnostics.router, prefix="/api/v1")
