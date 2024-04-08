"""Initial schema: vehicles and partitioned diagnostic_events

Revision ID: 001
Revises:
Create Date: 2024-04-08 09:00:00.000000

Key decisions documented here:
- diagnostic_events is RANGE partitioned by recorded_at (monthly partitions).
  Without partitioning, COUNT(*) and date-range queries on 10M+ rows required
  full sequential scans. With partitioning + date filter, the planner prunes
  to 1-2 monthly partitions instead.
- Indexes on (vehicle_id, recorded_at) and (fault_code) created in migration 002
  after benchmarking showed those were the hot access patterns.
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # vehicles — master reference table
    op.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id      SERIAL PRIMARY KEY,
            vin             VARCHAR(17) NOT NULL UNIQUE,
            make            VARCHAR(50) NOT NULL,
            model           VARCHAR(50) NOT NULL,
            year            SMALLINT NOT NULL,
            fuel_type       VARCHAR(20) NOT NULL DEFAULT 'PETROL',
            engine_displacement_cc INTEGER,
            transmission_type VARCHAR(20),
            odometer_km     INTEGER,
            last_seen_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_make ON vehicles (make)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_year ON vehicles (year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles (vin)")

    # diagnostic_events — partitioned by recorded_at (monthly RANGE partition)
    # This is the table that grows to 10M+ rows.
    op.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_events (
            event_id            BIGSERIAL,
            vehicle_id          INTEGER NOT NULL,
            event_type          VARCHAR(30) NOT NULL,
            severity            VARCHAR(10) NOT NULL,
            fault_code          VARCHAR(10),
            fault_description   TEXT,
            engine_temp_celsius NUMERIC(5,2),
            rpm                 INTEGER,
            vehicle_speed_kmh   NUMERIC(6,2),
            battery_voltage     NUMERIC(4,2),
            fuel_level_pct      NUMERIC(5,2),
            recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (event_id, recorded_at)
        ) PARTITION BY RANGE (recorded_at)
    """)

    # Create monthly partitions — 2023-01 through 2024-04 covers our seed data range
    months = [
        ("2023_01", "2023-01-01", "2023-02-01"),
        ("2023_02", "2023-02-01", "2023-03-01"),
        ("2023_03", "2023-03-01", "2023-04-01"),
        ("2023_04", "2023-04-01", "2023-05-01"),
        ("2023_05", "2023-05-01", "2023-06-01"),
        ("2023_06", "2023-06-01", "2023-07-01"),
        ("2023_07", "2023-07-01", "2023-08-01"),
        ("2023_08", "2023-08-01", "2023-09-01"),
        ("2023_09", "2023-09-01", "2023-10-01"),
        ("2023_10", "2023-10-01", "2023-11-01"),
        ("2023_11", "2023-11-01", "2023-12-01"),
        ("2023_12", "2023-12-01", "2024-01-01"),
        ("2024_01", "2024-01-01", "2024-02-01"),
        ("2024_02", "2024-02-01", "2024-03-01"),
        ("2024_03", "2024-03-01", "2024-04-01"),
        ("2024_04", "2024-04-01", "2024-05-01"),
        ("2024_05", "2024-05-01", "2024-06-01"),
    ]

    for suffix, start, end in months:
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS diagnostic_events_{suffix}
            PARTITION OF diagnostic_events
            FOR VALUES FROM ('{start}') TO ('{end}')
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS diagnostic_events CASCADE")
    op.execute("DROP TABLE IF EXISTS vehicles CASCADE")
