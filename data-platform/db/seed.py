"""
seed.py - Preload historical normal baseline events for border surveillance platform.

Conforms strictly to shared/schema.md:
- Sections 3 & 5: Fixed sources, zones, event_types, main features.
- Section 6: Event payload structure.
- Section 10: Baseline requires at least 30 events per source + zone.
- Section 11: Normal distributions and confidences.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

# Ensure local package import works regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import get_connection, get_db_path, init_db

SOURCES = ["camera", "wifi", "sensor", "satellite"]
ZONES = ["zone_1", "zone_2", "zone_3"]

SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "camera": {
        "event_type": "movement",
        "main_feature": "movement_level",
        "normal_avg": 0.15,
        "spread": 0.05,
    },
    "sensor": {
        "event_type": "vibration",
        "main_feature": "vibration_level",
        "normal_avg": 0.20,
        "spread": 0.05,
    },
    "wifi": {
        "event_type": "signal_change",
        "main_feature": "signal_change",
        "normal_avg": 0.15,
        "spread": 0.05,
    },
    "satellite": {
        "event_type": "surface_change",
        "main_feature": "surface_change",
        "normal_avg": 0.10,
        "spread": 0.05,
    },
}


def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp float to [min_val, max_val]."""
    return max(min_val, min(max_val, val))


def generate_seed_events(
    events_per_group: int = 40,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Generate normal events for all 12 source + zone combinations.
    Produces enough events (>= 30 per group) for Person 2's baseline engine.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    events: list[dict[str, Any]] = []
    event_counter = 0

    # Calculate time step so all events are ordered chronologically
    total_slots = events_per_group * len(SOURCES) * len(ZONES)
    start_time = end_time - timedelta(seconds=total_slots * 5)

    # Generate in interleaved rounds to simulate parallel real-time sensor streams
    current_time = start_time
    for _ in range(events_per_group):
        for zone in ZONES:
            for source in SOURCES:
                cfg = SOURCE_CONFIG[source]
                event_counter += 1

                raw_val = random.gauss(cfg["normal_avg"], cfg["spread"])
                feature_val = round(clamp(raw_val), 4)
                confidence = round(random.uniform(0.80, 0.99), 2)
                timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

                event = {
                    "event_id": f"evt_seed_{event_counter:04d}",
                    "source": source,
                    "zone": zone,
                    "timestamp": timestamp,
                    "event_type": cfg["event_type"],
                    "features": {cfg["main_feature"]: feature_val},
                    "confidence": confidence,
                }
                events.append(event)
                current_time += timedelta(seconds=5)

    return events


def seed_database(
    events_per_group: int = 40,
    db_path: Path | str | None = None,
    clear_existing: bool = False,
) -> int:
    """
    Populate SQLite database with historical seed events.
    Returns the total number of events inserted.
    """
    target_path = get_db_path(db_path)
    init_db(target_path)

    events = generate_seed_events(events_per_group=events_per_group)

    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        if clear_existing:
            cursor.execute("DELETE FROM events")

        cursor.executemany(
            """
            INSERT OR REPLACE INTO events (event_id, source, zone, timestamp, event_type, features, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e["event_id"],
                    e["source"],
                    e["zone"],
                    e["timestamp"],
                    e["event_type"],
                    json.dumps(e["features"]),
                    e["confidence"],
                )
                for e in events
            ],
        )
        conn.commit()

    return len(events)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with normal baseline events")
    parser.add_argument(
        "--count",
        type=int,
        default=40,
        help="Number of events per source+zone group (default: 40, min 30 required by engine)",
    )
    parser.add_argument("--clear", action="store_true", help="Clear existing events table before seeding")
    parser.add_argument("--path", type=str, default=None, help="Custom database file path")
    args = parser.parse_args()

    total_inserted = seed_database(
        events_per_group=args.count,
        db_path=args.path,
        clear_existing=args.clear,
    )

    db_target = get_db_path(args.path)
    print(f"Seeded {total_inserted} events into {db_target}")
    print(f"Groups: {len(SOURCES)} sources x {len(ZONES)} zones = {len(SOURCES) * len(ZONES)} groups")
    print(f"Events per group: {args.count} (meets >= 30 requirement for Person 2)")
