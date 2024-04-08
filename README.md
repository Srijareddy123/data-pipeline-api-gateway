# Data Pipeline API Gateway

Production-grade REST API gateway exposing vehicle diagnostic pipeline data. Built with FastAPI, raw psycopg2, PostgreSQL table partitioning, and Redis caching.

## Architecture

```
Client → FastAPI (rate limit → cache → repo → PostgreSQL)
                                    ↘ Redis (5min TTL)
```

- **FastAPI** — async-ready, auto-generated OpenAPI docs at `/docs`
- **PostgreSQL 16** — `diagnostic_events` is RANGE-partitioned by month; queries with date filters prune to 1–2 partitions instead of scanning 10M+ rows
- **Redis 7** — shared cache across all API instances; degrades gracefully if unavailable
- **Rate limiting** — sliding window via Redis sorted sets (100 req/60s per IP by default)
- **Raw psycopg2** — no ORM; every query is visible, every index choice is intentional

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check (DB + cache status) |
| GET | `/api/v1/vehicles` | List vehicles with filtering + pagination |
| GET | `/api/v1/vehicles/{id}` | Get vehicle by ID |
| GET | `/api/v1/vehicles/vin/{vin}` | Get vehicle by VIN |
| GET | `/api/v1/vehicles/{id}/summary` | Vehicle + event count summary |
| GET | `/api/v1/diagnostics/events` | List diagnostic events with filtering |
| GET | `/api/v1/diagnostics/events/{id}` | Get event by ID |
| GET | `/api/v1/diagnostics/fault-codes` | Top fault codes by occurrence |
| GET | `/api/v1/diagnostics/stats` | Aggregate diagnostic statistics |

All list endpoints support `page`, `page_size`, `sort_by`, `sort_order` and return a paginated envelope:

```json
{
  "data": [...],
  "total": 50000,
  "page": 1,
  "page_size": 50,
  "total_pages": 1000,
  "has_next": true,
  "has_prev": false
}
```

## Quickstart

### Docker (recommended)

```bash
# Build, migrate, start
make up

# Seed with 500 vehicles + 50k events
make seed

# Check it's running
make health
```

### Local dev

```bash
# Install dependencies
make install

# Start Postgres + Redis via Docker, then run API locally
docker compose up -d postgres redis
docker compose run --rm migrate
uvicorn src.api.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Configuration

All settings via environment variables. Defaults work for local Docker Compose — no changes needed for local dev.

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_DB` | `pipeline_db` | Database name |
| `POSTGRES_USER` | `pipeline_user` | DB user |
| `POSTGRES_PASSWORD` | `pipeline_pass` | DB password |
| `REDIS_HOST` | `localhost` | Redis host |
| `CACHE_TTL_SECONDS` | `300` | List query cache TTL |
| `CACHE_TTL_LONG_SECONDS` | `3600` | Lookup cache TTL |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window |

Copy `.env.example` to `.env` for local overrides.

**Production swap:** set `POSTGRES_HOST` to your RDS endpoint and `REDIS_HOST` to your ElastiCache endpoint. No code changes required.

## Development

```bash
make test          # Run tests with coverage (target: 80%+)
make test-fast     # Run tests without coverage report
make lint          # ruff
make format        # black
make type-check    # mypy
```

### Seed data

```bash
# Default: 500 vehicles, 50k events
python scripts/seed.py

# Custom scale
python scripts/seed.py --vehicles 1000 --events 100000
```

## Database schema

```sql
vehicles (
    vehicle_id SERIAL PRIMARY KEY,
    vin        VARCHAR(17) UNIQUE,
    make, model, year, fuel_type,
    engine_displacement_cc, transmission_type,
    odometer_km, last_seen_at, created_at
)

diagnostic_events (           -- RANGE partitioned by recorded_at (monthly)
    event_id     BIGSERIAL,
    vehicle_id   INTEGER,
    event_type, severity, fault_code, fault_description,
    engine_temp_celsius, rpm, vehicle_speed_kmh,
    battery_voltage, fuel_level_pct, recorded_at
)
```

Indexes on `(vehicle_id, recorded_at DESC)`, `fault_code`, `severity`, and `event_type` — added after profiling with `EXPLAIN ANALYZE` on a 10M-row dataset.

## Project structure

```
src/
├── api/
│   ├── main.py               # FastAPI app, lifespan, middleware
│   └── v1/
│       ├── routes/           # health, vehicles, diagnostics
│       └── schemas/          # Pydantic request/response models
├── core/
│   ├── config.py             # pydantic-settings, env vars
│   ├── database.py           # psycopg2 connection pool
│   ├── cache.py              # Redis cache layer
│   └── rate_limit.py         # Sliding window rate limiter
├── repositories/             # Raw SQL queries
└── tasks/
    └── background.py         # Post-response background tasks
migrations/                   # Alembic migrations
scripts/
    └── seed.py               # Faker-based seed data generator
tests/                        # pytest, 93% coverage
```
