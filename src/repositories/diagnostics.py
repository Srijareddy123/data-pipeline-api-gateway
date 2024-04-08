"""
Diagnostic event queries against the partitioned table.

The diagnostic_events table is range-partitioned by month on recorded_at.
Postgres partition pruning kicks in whenever the WHERE clause includes
a recorded_at range — the planner only scans relevant monthly partitions
instead of the full 10M+ row table.

Query pattern rule: always include a date range filter in production queries.
Without it, Postgres scans all partitions and performance degrades to a
sequential scan of the entire table.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.core.database import get_db, QueryTimer
from src.core.logging import get_logger

logger = get_logger(__name__)

_SORTABLE = {
    "event_id", "vehicle_id", "recorded_at", "severity",
    "engine_temp_celsius", "rpm", "vehicle_speed_kmh",
}


def list_diagnostic_events(
    vehicle_id: Optional[int],
    vin: Optional[str],
    event_type: Optional[str],
    severity: Optional[str],
    fault_code: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    min_engine_temp: Optional[float],
    max_engine_temp: Optional[float],
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    col = sort_by if sort_by in _SORTABLE else "recorded_at"
    direction = "ASC" if sort_order == "asc" else "DESC"

    conds: list[str] = []
    params: list = []

    if vehicle_id is not None:
        conds.append("e.vehicle_id = %s")
        params.append(vehicle_id)
    if vin:
        conds.append("v.vin = %s")
        params.append(vin)
    if event_type:
        conds.append("e.event_type = %s")
        params.append(event_type)
    if severity:
        conds.append("e.severity = %s")
        params.append(severity)
    if fault_code:
        conds.append("e.fault_code = %s")
        params.append(fault_code)
    if date_from:
        conds.append("e.recorded_at >= %s")
        params.append(date_from)
    if date_to:
        conds.append("e.recorded_at <= %s")
        params.append(date_to)
    if min_engine_temp is not None:
        conds.append("e.engine_temp_celsius >= %s")
        params.append(min_engine_temp)
    if max_engine_temp is not None:
        conds.append("e.engine_temp_celsius <= %s")
        params.append(max_engine_temp)

    where = "WHERE " + " AND ".join(conds) if conds else ""
    join = "JOIN vehicles v ON e.vehicle_id = v.vehicle_id" if vin else "JOIN vehicles v ON e.vehicle_id = v.vehicle_id"

    with get_db() as cur:
        with QueryTimer("events_count") as t:
            cur.execute(
                f"SELECT COUNT(*) AS total FROM diagnostic_events e {join} {where}",
                params,
            )
            total = cur.fetchone()["total"]

        with QueryTimer("events_list") as t:
            cur.execute(
                f"""
                SELECT e.event_id, e.vehicle_id, v.vin, e.event_type, e.severity,
                       e.fault_code, e.fault_description, e.engine_temp_celsius,
                       e.rpm, e.vehicle_speed_kmh, e.battery_voltage,
                       e.fuel_level_pct, e.recorded_at
                FROM diagnostic_events e
                {join}
                {where}
                ORDER BY {col} {direction}
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

    logger.info(json.dumps({"query": "events_list", "duration_ms": round(t.duration_ms, 2), "rows": len(rows)}))
    return rows, total


def get_event_by_id(event_id: int) -> dict | None:
    with get_db() as cur:
        cur.execute(
            """
            SELECT e.event_id, e.vehicle_id, v.vin, e.event_type, e.severity,
                   e.fault_code, e.fault_description, e.engine_temp_celsius,
                   e.rpm, e.vehicle_speed_kmh, e.battery_voltage,
                   e.fuel_level_pct, e.recorded_at
            FROM diagnostic_events e
            JOIN vehicles v ON e.vehicle_id = v.vehicle_id
            WHERE e.event_id = %s
            """,
            (event_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_fault_code_summary(limit: int = 20) -> list[dict]:
    with get_db() as cur:
        with QueryTimer("fault_code_summary") as t:
            cur.execute(
                """
                SELECT
                    fault_code,
                    fault_description,
                    COUNT(*) AS occurrence_count,
                    COUNT(DISTINCT vehicle_id) AS affected_vehicles,
                    MIN(recorded_at) AS first_seen,
                    MAX(recorded_at) AS last_seen
                FROM diagnostic_events
                WHERE fault_code IS NOT NULL
                GROUP BY fault_code, fault_description
                ORDER BY occurrence_count DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    logger.info(json.dumps({"query": "fault_summary", "duration_ms": round(t.duration_ms, 2)}))
    return rows


def get_diagnostic_stats() -> dict:
    with get_db() as cur:
        with QueryTimer("diagnostic_stats") as t:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_events,
                    COUNT(*) FILTER (WHERE recorded_at >= NOW() - INTERVAL '24 hours') AS events_last_24h,
                    COUNT(*) FILTER (WHERE recorded_at >= NOW() - INTERVAL '7 days') AS events_last_7d,
                    COUNT(*) FILTER (WHERE severity = 'CRITICAL') AS critical_events,
                    COUNT(DISTINCT vehicle_id) AS unique_vehicles
                FROM diagnostic_events
                """
            )
            row = dict(cur.fetchone())
    logger.info(json.dumps({"query": "diagnostic_stats", "duration_ms": round(t.duration_ms, 2)}))
    return row
