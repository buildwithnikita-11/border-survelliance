"""
database.py - Database setup and operations for border surveillance data platform.

Adheres strictly to shared/schema.md (sections 3, 6, 8).
Owns creation of both 'events' and 'alerts' tables.
"""

import json
import os
from pathlib import Path
import sqlite3
from typing import Any

# Default path: data/situational.db at workspace root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "situational.db"


def get_db_path(override_path: Path | str | None = None) -> Path:
    """Get the active database file path."""
    if override_path:
        return Path(override_path)
    env_path = os.environ.get("SITUATIONAL_DB_PATH") or os.environ.get("DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection configured for concurrent access."""
    target_path = get_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: Path | str | None = None, drop_existing: bool = False) -> None:
    """
    Initialize SQLite database and create both events and alerts tables.
    Matches schema.md section 8 exactly.
    """
    target_path = get_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(target_path) as conn:
        cursor = conn.cursor()

        if drop_existing:
            cursor.execute("DROP TABLE IF EXISTS events")
            cursor.execute("DROP TABLE IF EXISTS alerts")

        # Table events per schema.md section 8
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                zone TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                features TEXT NOT NULL,
                confidence REAL NOT NULL
            )
            """
        )

        # Table alerts per schema.md section 8
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                zone TEXT NOT NULL,
                created_at TEXT NOT NULL,
                time_window_start TEXT NOT NULL,
                time_window_end TEXT NOT NULL,
                score REAL NOT NULL,
                evidence TEXT NOT NULL,
                status TEXT NOT NULL,
                analyst_note TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # Indexing for query performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_lookup ON events (source, zone, timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alerts (created_at DESC, status)"
        )
        conn.commit()


def save_event(event: dict[str, Any], db_path: Path | str | None = None) -> dict[str, Any]:
    """
    Insert an event record into the events table.
    Expects event dict conforming to schema.md section 6.
    """
    features_val = event.get("features", {})
    if not isinstance(features_val, str):
        features_json = json.dumps(features_val)
    else:
        features_json = features_val

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (event_id, source, zone, timestamp, event_type, features, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["source"],
                event["zone"],
                event["timestamp"],
                event["event_type"],
                features_json,
                float(event["confidence"]),
            ),
        )
        conn.commit()

    return event


def get_events(
    zone: str | None = None,
    source: str | None = None,
    since: str | None = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch events from the database with optional filters.
    Returns list of event dicts matching schema.md section 6.
    """
    query = "SELECT event_id, source, zone, timestamp, event_type, features, confidence FROM events"
    filters = []
    params: list[Any] = []

    if zone is not None:
        filters.append("zone = ?")
        params.append(zone)
    if source is not None:
        filters.append("source = ?")
        params.append(source)
    if since is not None:
        filters.append("timestamp >= ?")
        params.append(since)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY timestamp ASC"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    for row in rows:
        features_raw = row["features"]
        try:
            features_dict = json.loads(features_raw) if isinstance(features_raw, str) else features_raw
        except Exception:
            features_dict = {}

        results.append(
            {
                "event_id": row["event_id"],
                "source": row["source"],
                "zone": row["zone"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "features": features_dict,
                "confidence": row["confidence"],
            }
        )

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Situational Awareness SQLite Database")
    parser.add_argument("--reset", action="store_true", help="Drop existing tables and recreate")
    parser.add_argument("--path", type=str, default=None, help="Custom database file path")
    args = parser.parse_args()

    db_target = get_db_path(args.path)
    init_db(db_path=db_target, drop_existing=args.reset)
    print(f"Database successfully initialized at: {db_target}")

    with get_connection(db_target) as c:
        tbls = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"Verified tables in database: {tbls}")
