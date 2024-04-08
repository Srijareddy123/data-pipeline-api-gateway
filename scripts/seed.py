"""
Seed script — populates vehicles and diagnostic_events with realistic fake data.

Usage:
    python scripts/seed.py                  # 500 vehicles, 50,000 events
    python scripts/seed.py --vehicles 1000 --events 100000
    docker compose --profile seed up seed

Requires: Faker (included in dev dependencies via pyproject.toml)
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg2
from faker import Faker

from src.core.config import get_settings

fake = Faker()
Faker.seed(42)
random.seed(42)

MAKES_MODELS = {
    "Toyota": ["Corolla", "Camry", "RAV4", "Hilux", "Fortuner"],
    "Honda": ["Accord", "Civic", "CR-V", "City", "Jazz"],
    "Ford": ["Ranger", "F-150", "Focus", "Mustang", "EcoSport"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "M3"],
    "Mercedes": ["C-Class", "E-Class", "GLC", "GLE", "A-Class"],
    "Hyundai": ["Tucson", "Santa Fe", "Elantra", "i20", "Creta"],
    "Volkswagen": ["Golf", "Polo", "Tiguan", "Passat", "T-Roc"],
    "Kia": ["Sportage", "Sorento", "Cerato", "Seltos", "Picanto"],
}

FUEL_TYPES = ["PETROL", "DIESEL", "HYBRID", "ELECTRIC", "LPG"]
TRANSMISSION_TYPES = ["AUTOMATIC", "MANUAL", "CVT", "DCT"]

EVENT_TYPES = ["FAULT", "WARNING", "TELEMETRY", "MAINTENANCE", "SENSOR_DATA"]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SEVERITY_WEIGHTS = [50, 30, 15, 5]

FAULT_CODES = [
    ("P0300", "Random misfire detected"),
    ("P0171", "System too lean - Bank 1"),
    ("P0420", "Catalyst system efficiency below threshold"),
    ("P0401", "EGR insufficient flow detected"),
    ("P0113", "Intake air temperature sensor high"),
    ("P0128", "Coolant thermostat below regulating temperature"),
    ("P0562", "System voltage low"),
    ("P0700", "Transmission control system malfunction"),
    ("B0001", "Airbag deployment loop open"),
    ("C0035", "Left front wheel speed sensor circuit"),
    ("U0100", "Lost communication with ECM/PCM A"),
    ("P0016", "Crankshaft/camshaft position correlation"),
]


def _rand_vin() -> str:
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "".join(random.choices(chars, k=17))


def seed(n_vehicles: int, n_events: int) -> None:
    s = get_settings()
    conn = psycopg2.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        dbname=s.postgres_db,
        user=s.postgres_user,
        password=s.postgres_password,
    )
    cur = conn.cursor()

    print(f"Seeding {n_vehicles} vehicles...")
    vins_used: set[str] = set()
    vehicle_ids: list[int] = []

    for _ in range(n_vehicles):
        make = random.choice(list(MAKES_MODELS))
        model = random.choice(MAKES_MODELS[make])
        year = random.randint(2015, 2024)
        fuel = random.choice(FUEL_TYPES)
        transmission = random.choice(TRANSMISSION_TYPES)

        while True:
            vin = _rand_vin()
            if vin not in vins_used:
                vins_used.add(vin)
                break

        cur.execute(
            """
            INSERT INTO vehicles (vin, make, model, year, fuel_type,
                engine_displacement_cc, transmission_type, odometer_km,
                last_seen_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (vin) DO NOTHING
            RETURNING vehicle_id
            """,
            (
                vin, make, model, year, fuel,
                random.randint(1000, 5000),
                transmission,
                random.randint(5000, 200000),
                fake.date_time_between(start_date="-3m", end_date="now", tzinfo=timezone.utc),
                fake.date_time_between(start_date="-2y", end_date="-6m", tzinfo=timezone.utc),
            ),
        )
        row = cur.fetchone()
        if row:
            vehicle_ids.append(row[0])

    conn.commit()
    print(f"  Inserted {len(vehicle_ids)} vehicles.")

    if not vehicle_ids:
        print("No vehicle IDs returned — aborting event seed.")
        conn.close()
        return

    print(f"Seeding {n_events} diagnostic events...")

    start_dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2024, 4, 30, tzinfo=timezone.utc)
    span_seconds = int((end_dt - start_dt).total_seconds())

    batch: list[tuple] = []
    batch_size = 2000

    for i in range(n_events):
        vehicle_id = random.choice(vehicle_ids)
        event_type = random.choice(EVENT_TYPES)
        severity = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
        recorded_at = start_dt + timedelta(seconds=random.randint(0, span_seconds))

        fault_code = fault_desc = None
        if event_type == "FAULT":
            code, desc = random.choice(FAULT_CODES)
            fault_code, fault_desc = code, desc

        batch.append((
            vehicle_id,
            event_type,
            severity,
            fault_code,
            fault_desc,
            round(random.uniform(70, 120), 2) if random.random() > 0.1 else None,
            random.randint(600, 6500) if random.random() > 0.1 else None,
            round(random.uniform(0, 180), 2) if random.random() > 0.1 else None,
            round(random.uniform(11.5, 14.5), 2) if random.random() > 0.2 else None,
            round(random.uniform(5, 100), 2) if random.random() > 0.2 else None,
            recorded_at,
        ))

        if len(batch) >= batch_size:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO diagnostic_events
                    (vehicle_id, event_type, severity, fault_code, fault_description,
                     engine_temp_celsius, rpm, vehicle_speed_kmh,
                     battery_voltage, fuel_level_pct, recorded_at)
                VALUES %s
                """,
                batch,
            )
            conn.commit()
            batch.clear()
            print(f"  {min(i + 1, n_events):,} / {n_events:,}")

    if batch:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO diagnostic_events
                (vehicle_id, event_type, severity, fault_code, fault_description,
                 engine_temp_celsius, rpm, vehicle_speed_kmh,
                 battery_voltage, fuel_level_pct, recorded_at)
            VALUES %s
            """,
            batch,
        )
        conn.commit()

    cur.close()
    conn.close()
    print(f"Done. {n_events:,} events inserted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the pipeline database")
    parser.add_argument("--vehicles", type=int, default=500)
    parser.add_argument("--events", type=int, default=50_000)
    args = parser.parse_args()
    seed(args.vehicles, args.events)
