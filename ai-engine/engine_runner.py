"""
engine_runner.py - Live execution engine for border surveillance AI system.

Reads events from SQLite, runs anomaly detection, correlation, and scoring,
and manages alert lifecycle per shared/schema.md (sections 6, 7, 8, 10).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

# Ensure ai-engine directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from anomaly_detector import find_anomalies
from correlator import correlate
from fake_data import make_test_scenario
from prioritizer import prioritize

# Default database path relative to this file matching section 8
DEFAULT_DB_PATH = Path(__file__).resolve().parent / ".." / "data" / "situational.db"


def get_db_path() -> Path:
    """Return database path relative to this file."""
    return DEFAULT_DB_PATH


def check_database(db_path: Path | str) -> tuple[bool, str]:
    """
    Check if the database file and required tables ('events', 'alerts') exist.
    Returns (True, message) if valid, otherwise (False, clear_error_message).
    """
    target = Path(db_path)
    if not target.exists():
        return False, f"Database file does not exist at '{db_path}'."

    try:
        conn = sqlite3.connect(str(target))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        missing = [t for t in ("events", "alerts") if t not in tables]
        if missing:
            return False, f"Required table(s) {', '.join(missing)} do not exist in database at '{db_path}'."
        return True, "Database and required tables exist."
    except Exception as exc:
        return False, f"Failed to access database at '{db_path}': {exc}"


def load_events(
    conn: sqlite3.Connection, since_id: int | None = None
) -> tuple[list[dict], int | None]:
    """
    Read rows from 'events' table.

    - If since_id is given, read only rows with rowid > since_id (ascending).
    - Otherwise, read the last 500 rows (in ascending chronological order).
    - Parse 'features' from JSON text into a dict for each row.
    - Return list of events matching section 6 and highest rowid seen.
    """
    cursor = conn.cursor()
    if since_id is not None:
        cursor.execute(
            """
            SELECT rowid, event_id, source, zone, timestamp, event_type, features, confidence
            FROM events
            WHERE rowid > ?
            ORDER BY rowid ASC
            """,
            (since_id,),
        )
    else:
        cursor.execute(
            """
            SELECT rowid, event_id, source, zone, timestamp, event_type, features, confidence
            FROM (
                SELECT rowid, event_id, source, zone, timestamp, event_type, features, confidence
                FROM events
                ORDER BY rowid DESC
                LIMIT 500
            )
            ORDER BY rowid ASC
            """
        )

    rows = cursor.fetchall()
    events: list[dict] = []
    max_rowid: int | None = since_id

    for row in rows:
        rowid = row[0]
        event_id = row[1]
        source = row[2]
        zone = row[3]
        timestamp = row[4]
        event_type = row[5]
        features_raw = row[6]
        confidence = row[7]

        if max_rowid is None or rowid > max_rowid:
            max_rowid = rowid

        if isinstance(features_raw, str):
            try:
                features = json.loads(features_raw)
            except Exception:
                features = {}
        elif isinstance(features_raw, dict):
            features = features_raw
        else:
            features = {}

        event = {
            "event_id": event_id,
            "source": source,
            "zone": zone,
            "timestamp": timestamp,
            "event_type": event_type,
            "features": features,
            "confidence": float(confidence),
        }
        events.append(event)

    return events, max_rowid


def load_pending_alerts(conn: sqlite3.Connection, zone: str) -> list[dict]:
    """
    Read rows from 'alerts' where status is 'pending' and zone matches.
    Parse 'evidence' JSON into list matching section 7 format.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT alert_id, type, zone, created_at, time_window_start, time_window_end, score, evidence, status, analyst_note
        FROM alerts
        WHERE status = 'pending' AND zone = ?
        """,
        (zone,),
    )
    rows = cursor.fetchall()
    alerts: list[dict] = []

    for row in rows:
        evidence_raw = row[7]
        if isinstance(evidence_raw, str):
            try:
                evidence = json.loads(evidence_raw)
            except Exception:
                evidence = []
        elif isinstance(evidence_raw, list):
            evidence = evidence_raw
        else:
            evidence = []

        alert = {
            "alert_id": row[0],
            "type": row[1],
            "zone": row[2],
            "created_at": row[3],
            "time_window_start": row[4],
            "time_window_end": row[5],
            "score": float(row[6]),
            "evidence": evidence,
            "status": row[8],
            "analyst_note": row[9] if row[9] is not None else "",
        }
        alerts.append(alert)

    return alerts


def get_next_alert_id(conn: sqlite3.Connection) -> str:
    """Find highest existing numeric suffix in alerts table and add 1."""
    cursor = conn.cursor()
    cursor.execute("SELECT alert_id FROM alerts")
    rows = cursor.fetchall()
    max_num = 0
    for r in rows:
        aid = r[0] if isinstance(r, (tuple, list)) else r["alert_id"]
        if aid and isinstance(aid, str):
            match = re.search(r"(\d+)$", aid)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
    return f"alert_{max_num + 1:04d}"


def save_alert(conn: sqlite3.Connection, alert: dict) -> dict:
    """
    Save alert dictionary to the database.

    - Checks pending alerts for the same zone.
    - If one has an overlapping time window (time_window_start < alert.time_window_end
      and time_window_end > alert.time_window_start), UPDATE that existing row:
      replace evidence, score, type, time_window_end, and created_at. Keep existing
      alert_id, status, and analyst_note untouched.
    - Otherwise INSERT a new row with alert_id formatted as 'alert_XXXX'.
    - Commits after every save and prints action, alert_id, zone, and score.
    """
    zone = alert["zone"]
    pending_alerts = load_pending_alerts(conn, zone)

    matched_alert: dict | None = None
    for p in pending_alerts:
        if (
            p["time_window_start"] < alert["time_window_end"]
            and p["time_window_end"] > alert["time_window_start"]
        ):
            matched_alert = p
            break

    cursor = conn.cursor()
    evidence_json = json.dumps(alert.get("evidence", []))

    if matched_alert is not None:
        alert_id = matched_alert["alert_id"]
        alert["alert_id"] = alert_id
        alert["time_window_start"] = matched_alert["time_window_start"]
        alert["status"] = matched_alert["status"]
        alert["analyst_note"] = matched_alert["analyst_note"]

        cursor.execute(
            """
            UPDATE alerts
            SET evidence = ?, score = ?, type = ?, time_window_end = ?, created_at = ?
            WHERE alert_id = ?
            """,
            (
                evidence_json,
                float(alert["score"]),
                alert["type"],
                alert["time_window_end"],
                alert["created_at"],
                alert_id,
            ),
        )
        conn.commit()
        print(f"UPDATE alert {alert_id} ({zone}, score: {alert['score']})", flush=True)
    else:
        alert_id = get_next_alert_id(conn)
        alert["alert_id"] = alert_id
        cursor.execute(
            """
            INSERT INTO alerts (
                alert_id, type, zone, created_at, time_window_start, time_window_end,
                score, evidence, status, analyst_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                alert["type"],
                zone,
                alert["created_at"],
                alert["time_window_start"],
                alert["time_window_end"],
                float(alert["score"]),
                evidence_json,
                alert.get("status", "pending"),
                alert.get("analyst_note", ""),
            ),
        )
        conn.commit()
        print(f"INSERT alert {alert_id} ({zone}, score: {alert['score']})", flush=True)

    return alert


def run_once(
    conn: sqlite3.Connection, history: list[dict], since_id: int | None
) -> tuple[int | None, list[dict]]:
    """
    Run one iteration of the pipeline.

    - Loads new events using since_id.
    - If none, returns same since_id and empty alert list.
    - Adds new events to history (capped at last 2000).
    - Runs find_anomalies, correlate (with UTC now), prioritize, and save_alert.
    - Returns updated since_id and saved alerts list.
    """
    new_events, new_since_id = load_events(conn, since_id=since_id)
    if not new_events:
        return since_id, []

    history.extend(new_events)
    if len(history) > 2000:
        del history[:-2000]

    anomalies = find_anomalies(new_events, history)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alerts = correlate(anomalies, now=now_utc)

    prioritized_alerts = prioritize(alerts)

    saved_alerts: list[dict] = []
    for a in prioritized_alerts:
        save_alert(conn, a)
        saved_alerts.append(a)

    return new_since_id, saved_alerts


def run_forever(poll_seconds: int = 5, max_iterations: int | None = None) -> None:
    """
    Main loop polling for new events every poll_seconds.
    Loads last 500 events as starting history, sets since_id from them,
    and runs pipeline repeatedly.
    """
    db_path = get_db_path()
    valid, msg = check_database(db_path)
    if not valid:
        print(msg, flush=True)
        return

    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        history, since_id = load_events(conn, since_id=None)
        print(f"Loaded {len(history)} initial events into history. Starting since_id: {since_id}", flush=True)

        iteration = 0
        while True:
            try:
                since_id, saved_alerts = run_once(conn, history, since_id)
            except Exception as exc:
                print(f"Error in engine runner iteration: {exc}", flush=True)

            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                break

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("Stopping engine runner.", flush=True)
    finally:
        conn.close()


def run_fallback_test() -> bool:
    """
    In-memory fallback test when database does not exist.
    Creates schema, inserts make_test_scenario events, runs run_once twice,
    and verifies no duplicate rows are created.
    """
    print("\n--- Fallback In-Memory Test (Testing pipeline without database file) ---", flush=True)
    mem_conn = sqlite3.connect(":memory:")

    # Create tables matching section 8 exactly
    mem_conn.execute(
        """
        CREATE TABLE events (
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
    mem_conn.execute(
        """
        CREATE TABLE alerts (
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
    mem_conn.commit()

    scenario_events = make_test_scenario()
    for e in scenario_events:
        features_json = json.dumps(e["features"]) if isinstance(e["features"], dict) else e["features"]
        mem_conn.execute(
            """
            INSERT INTO events (event_id, source, zone, timestamp, event_type, features, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["event_id"],
                e["source"],
                e["zone"],
                e["timestamp"],
                e["event_type"],
                features_json,
                float(e["confidence"]),
            ),
        )
    mem_conn.commit()
    print(f"Inserted {len(scenario_events)} scenario events into in-memory database.", flush=True)

    # First pass: run run_once
    print("\nRunning run_once (Pass 1)...", flush=True)
    history: list[dict] = []
    since_id, saved_alerts = run_once(mem_conn, history, since_id=0)
    print(f"Pass 1 saved {len(saved_alerts)} alert(s):", flush=True)
    for a in saved_alerts:
        print(f"  [{a['alert_id']}] Zone: {a['zone']}, Type: {a['type']}, Score: {a['score']}", flush=True)

    count_after_first = mem_conn.execute("SELECT count(*) FROM alerts").fetchone()[0]

    # Second pass: run run_once a second time right after
    print("\nRunning run_once a second time right after (Pass 2, duplicate prevention check)...", flush=True)
    since_id_2, saved_alerts_2 = run_once(mem_conn, list(history), since_id=0)
    count_after_second = mem_conn.execute("SELECT count(*) FROM alerts").fetchone()[0]

    print(f"\nAlert count after Run 1: {count_after_first}", flush=True)
    print(f"Alert count after Run 2: {count_after_second}", flush=True)

    if count_after_second == count_after_first and count_after_first > 0:
        print("PASS: No duplicate rows created for the same alert.", flush=True)
        mem_conn.close()
        return True
    else:
        print(f"FAIL: Expected {count_after_first} alerts, got {count_after_second}.", flush=True)
        mem_conn.close()
        return False


if __name__ == "__main__":
    db_path = get_db_path()
    db_exists, db_msg = check_database(db_path)

    # If --test-fallback argument is passed, force fallback test even if DB exists
    force_fallback = "--test-fallback" in sys.argv

    if not db_exists:
        # Test A: if the database or tables do not exist, print the clear message
        # and do fallback test instead without starting run_forever
        print(f"Test A: {db_msg}", flush=True)
        run_fallback_test()
    elif force_fallback:
        print(f"Test A: {db_msg} (--test-fallback flag provided)", flush=True)
        run_fallback_test()
    else:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            # Test B: call load_events with since_id=None and print how many
            # events were found and the field names of the first one.
            history, since_id = load_events(conn, since_id=None)
            print(f"Test B: Found {len(history)} events.", flush=True)
            if history:
                print(f"Test B: Field names of first event: {list(history[0].keys())}", flush=True)
            else:
                print("Test B: No events found in table.", flush=True)

            # Test C: call run_once one time using that history and print how many alerts were saved.
            since_id, saved_alerts = run_once(conn, history, since_id)
            print(f"Test C: {len(saved_alerts)} alerts saved.", flush=True)
        finally:
            conn.close()

        # Start live engine runner unless --once is requested
        if "--once" not in sys.argv:
            run_forever(poll_seconds=5)
