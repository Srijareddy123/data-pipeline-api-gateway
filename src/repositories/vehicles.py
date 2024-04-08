"""
Vehicle queries — raw psycopg2.

Spending 16 months at KPIT writing raw SQL before this project made it natural
to keep the ORM out. You see exactly what hits the database, exactly which
index gets used, and exactly why a query is slow when it is.
"""

from __future__ import annotations

import json
from typing import Optional

from src.core.database import get_db, QueryTimer
from src.core.logging import get_logger

logger = get_logger(__name__)

# Whitelist prevents SQL injection via sort_by parameter
_SORTABLE = {"vehicle_id", "make", "model", "year", "odometer_km", "last_seen_at", "created_at"}


def list_vehicles(
    make: Optional[str],
    model: Optional[str],
    year_from: Optional[int],
    year_to: Optional[int],
    fuel_type: Optional[str],
    min_odometer_km: Optional[int],
    max_odometer_km: Optional[int],
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    col = sort_by if sort_by in _SORTABLE else "vehicle_id"
    direction = "ASC" if sort_order == "asc" else "DESC"

    conds: list[str] = []
    params: list = []

    if make:
        conds.append("make ILIKE %s")
        params.append(f"%{make}%")
    if model:
        conds.append("model ILIKE %s")
        params.append(f"%{model}%")
    if year_from is not None:
        conds.append("year >= %s")
        params.append(year_from)
    if year_to is not None:
        conds.append("year <= %s")
        params.append(year_to)
    if fuel_type:
        conds.append("fuel_type = %s")
        params.append(fuel_type)
    if min_odometer_km is not None:
        conds.append("odometer_km >= %s")
        params.append(min_odometer_km)
    if max_odometer_km is not None:
        conds.append("odometer_km <= %s")
        params.append(max_odometer_km)

    where = "WHERE " + " AND ".join(conds) if conds else ""

    with get_db() as cur:
        with QueryTimer("vehicles_count") as t:
            cur.execute(f"SELECT COUNT(*) AS total FROM vehicles {where}", params)
            total = cur.fetchone()["total"]

        with QueryTimer("vehicles_list") as t:
            cur.execute(
                f"""
                SELECT vehicle_id, vin, make, model, year, fuel_type,
                       engine_displacement_cc, transmission_type,
                       odometer_km, last_seen_at, created_at
                FROM vehicles {where}
                ORDER BY {col} {direction}
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

    logger.info(json.dumps({"query": "vehicles_list", "duration_ms": round(t.duration_ms, 2), "rows": len(rows)}))
    return rows, total


def get_vehicle_by_id(vehicle_id: int) -> dict | None:
    with get_db() as cur:
        cur.execute(
            """
            SELECT vehicle_id, vin, make, model, year, fuel_type,
                   engine_displacement_cc, transmission_type,
                   odometer_km, last_seen_at, created_at
            FROM vehicles WHERE vehicle_id = %s
            """,
            (vehicle_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_vehicle_by_vin(vin: str) -> dict | None:
    with get_db() as cur:
        cur.execute(
            """
            SELECT vehicle_id, vin, make, model, year, fuel_type,
                   engine_displacement_cc, transmission_type,
                   odometer_km, last_seen_at, created_at
            FROM vehicles WHERE vin = %s
            """,
            (vin,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_vehicle_summary(vehicle_id: int) -> dict | None:
    with get_db() as cur:
        cur.execute(
            """
            SELECT v.vehicle_id, v.vin, v.make, v.model, v.year,
                   COUNT(e.event_id) AS total_events,
                   MAX(e.recorded_at) AS last_event_at
            FROM vehicles v
            LEFT JOIN diagnostic_events e ON v.vehicle_id = e.vehicle_id
            WHERE v.vehicle_id = %s
            GROUP BY v.vehicle_id, v.vin, v.make, v.model, v.year
            """,
            (vehicle_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
