"""
verify_all_tests.py - Test suite validating all 9 contract requirements.

TEST 1: Fresh DB init -> verify tables 'events' and 'alerts'
TEST 2: POST valid event -> HTTP 200, event_id generated, stored, matches contract
TEST 3: POST invalid source -> HTTP 422, not stored
TEST 4: POST missing main feature -> HTTP 422, not stored
TEST 5: POST main feature outside 0-1 -> HTTP 422, not stored
TEST 6: GET /events filtering by source, zone, and source+zone
TEST 7: Run all simulators -> confirm valid events
TEST 8: Trigger anomaly command -> confirm vibration_level around 0.90
TEST 9: Run seed script -> confirm >= 30 events for all 12 source+zone groups
"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from fastapi.testclient import TestClient

# Ensure imports resolve
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir / "db"))
sys.path.insert(0, str(base_dir / "ingestion_api"))
sys.path.insert(0, str(base_dir / "simulators"))

from database import DEFAULT_DB_PATH, get_connection, init_db
from main import app
from seed import seed_database

REQUIRED_EVENT_KEYS = {
    "event_id",
    "source",
    "zone",
    "timestamp",
    "event_type",
    "features",
    "confidence",
}


def run_tests():
    print("=" * 70)
    print("STARTING TEST SUITE FOR PERSON 1 DATA PLATFORM")
    print("=" * 70)

    # Use test database file
    test_db_path = base_dir / "test_situational.db"
    import os
    os.environ["SITUATIONAL_DB_PATH"] = str(test_db_path)

    # Clean up any leftover test db
    if test_db_path.exists():
        test_db_path.unlink()

    # -------------------------------------------------------------------------
    # TEST 1: Initialize a fresh database. Confirm both tables exist.
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Initializing fresh database...")
    init_db(db_path=test_db_path, drop_existing=True)
    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

    print(f"Discovered tables in database: {tables}")
    assert "events" in tables, "FAIL: 'events' table missing!"
    assert "alerts" in tables, "FAIL: 'alerts' table missing!"
    print("-> TEST 1 PASSED: Fresh database contains both 'events' and 'alerts' tables.")

    # -------------------------------------------------------------------------
    # TEST 2: POST one valid event.
    # -------------------------------------------------------------------------
    print("\n[TEST 2] POST one valid event...")
    client = TestClient(app)
    valid_payload = {
        "source": "wifi",
        "zone": "zone_2",
        "timestamp": "2026-09-28T19:30:00Z",
        "event_type": "signal_change",
        "features": {
            "signal_change": 0.72
        },
        "confidence": 0.88,
    }

    res = client.post("/events", json=valid_payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response Body: {res.json()}")

    assert res.status_code == 200, f"FAIL: Expected HTTP 200, got {res.status_code}"
    body = res.json()
    assert set(body.keys()) == REQUIRED_EVENT_KEYS, f"FAIL: Keys mismatch: {set(body.keys())}"
    assert "event_id" in body and body["event_id"].startswith("evt_"), "FAIL: event_id missing or invalid"
    assert body["source"] == "wifi"
    assert body["zone"] == "zone_2"
    assert body["features"] == {"signal_change": 0.72}
    assert body["confidence"] == 0.88

    # Verify event is stored in database
    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE event_id = ?", (body["event_id"],))
        stored = cursor.fetchone()
    assert stored is not None, "FAIL: Event was not stored in database!"
    print(f"Stored DB Row: event_id={stored['event_id']}, source={stored['source']}, features={stored['features']}")
    print("-> TEST 2 PASSED: Valid event returned HTTP 200, event_id generated, stored in DB, contract satisfied.")

    # -------------------------------------------------------------------------
    # TEST 3: POST an invalid source.
    # -------------------------------------------------------------------------
    print("\n[TEST 3] POST an invalid source ('radar')...")
    bad_source_payload = dict(valid_payload)
    bad_source_payload["source"] = "radar"

    res = client.post("/events", json=bad_source_payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response Body: {res.json()}")
    assert res.status_code == 422, f"FAIL: Expected HTTP 422, got {res.status_code}"

    # Verify not stored
    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events WHERE source = 'radar'")
        count = cursor.fetchone()[0]
    assert count == 0, "FAIL: Invalid event was stored in database!"
    print("-> TEST 3 PASSED: Invalid source returned HTTP 422 and was NOT stored.")

    # -------------------------------------------------------------------------
    # TEST 4: POST an event missing its main feature.
    # -------------------------------------------------------------------------
    print("\n[TEST 4] POST event missing main feature for camera ('movement_level')...")
    missing_feature_payload = {
        "source": "camera",
        "zone": "zone_1",
        "timestamp": "2026-09-28T19:30:00Z",
        "event_type": "movement",
        "features": {
            "brightness": 0.5  # Extra feature, but main feature 'movement_level' is missing
        },
        "confidence": 0.90,
    }

    res = client.post("/events", json=missing_feature_payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response Body: {res.json()}")
    assert res.status_code == 422, f"FAIL: Expected HTTP 422, got {res.status_code}"

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events WHERE source = 'camera'")
        count = cursor.fetchone()[0]
    assert count == 0, "FAIL: Event missing main feature was stored in database!"
    print("-> TEST 4 PASSED: Missing main feature returned HTTP 422 and was NOT stored.")

    # -------------------------------------------------------------------------
    # TEST 5: POST an event whose main feature is outside 0-1.
    # -------------------------------------------------------------------------
    print("\n[TEST 5] POST event whose main feature value is outside 0-1 (1.45)...")
    out_of_range_payload = {
        "source": "sensor",
        "zone": "zone_3",
        "timestamp": "2026-09-28T19:30:00Z",
        "event_type": "vibration",
        "features": {
            "vibration_level": 1.45
        },
        "confidence": 0.85,
    }

    res = client.post("/events", json=out_of_range_payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response Body: {res.json()}")
    assert res.status_code == 422, f"FAIL: Expected HTTP 422, got {res.status_code}"

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events WHERE source = 'sensor'")
        count = cursor.fetchone()[0]
    assert count == 0, "FAIL: Out-of-range event was stored in database!"
    print("-> TEST 5 PASSED: Main feature outside 0-1 returned HTTP 422 and was NOT stored.")

    # -------------------------------------------------------------------------
    # TEST 6: POST events and test GET /events filtering.
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing GET /events filtering...")
    # Add known test events
    events_to_add = [
        {
            "source": "sensor",
            "zone": "zone_1",
            "timestamp": "2026-09-28T19:31:00Z",
            "event_type": "vibration",
            "features": {"vibration_level": 0.20},
            "confidence": 0.90,
        },
        {
            "source": "sensor",
            "zone": "zone_2",
            "timestamp": "2026-09-28T19:32:00Z",
            "event_type": "vibration",
            "features": {"vibration_level": 0.22},
            "confidence": 0.91,
        },
        {
            "source": "satellite",
            "zone": "zone_2",
            "timestamp": "2026-09-28T19:33:00Z",
            "event_type": "surface_change",
            "features": {"surface_change": 0.12},
            "confidence": 0.85,
        },
    ]

    for ev in events_to_add:
        r = client.post("/events", json=ev)
        assert r.status_code == 200

    # 1. GET /events
    res_all = client.get("/events")
    print(f"GET /events count: {len(res_all.json())}")
    # We had 1 from TEST 2 (wifi in zone_2) + 3 new = 4 total
    assert len(res_all.json()) == 4

    # 2. GET /events?source=sensor
    res_sensor = client.get("/events?source=sensor")
    print(f"GET /events?source=sensor count: {len(res_sensor.json())}")
    assert len(res_sensor.json()) == 2
    assert all(e["source"] == "sensor" for e in res_sensor.json())

    # 3. GET /events?zone=zone_2
    res_zone2 = client.get("/events?zone=zone_2")
    print(f"GET /events?zone=zone_2 count: {len(res_zone2.json())}")
    # wifi, sensor, satellite in zone_2 = 3
    assert len(res_zone2.json()) == 3
    assert all(e["zone"] == "zone_2" for e in res_zone2.json())

    # 4. GET /events?source=sensor&zone=zone_2
    res_sensor_zone2 = client.get("/events?source=sensor&zone=zone_2")
    print(f"GET /events?source=sensor&zone=zone_2 count: {len(res_sensor_zone2.json())}")
    assert len(res_sensor_zone2.json()) == 1
    assert res_sensor_zone2.json()[0]["source"] == "sensor"
    assert res_sensor_zone2.json()[0]["zone"] == "zone_2"
    print("-> TEST 6 PASSED: Filtering by zone, source, and combination works accurately.")

    # -------------------------------------------------------------------------
    # TEST 7: Run each simulator and confirm it produces valid events.
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Running each simulator and confirming valid events...")
    simulators = [
        ("camera_simulator.py", "camera", "movement", "movement_level"),
        ("wifi_simulator.py", "wifi", "signal_change", "signal_change"),
        ("sensor_simulator.py", "sensor", "vibration", "vibration_level"),
        ("satellite_input.py", "satellite", "surface_change", "surface_change"),
    ]

    for sim_file, expected_src, expected_type, expected_feature in simulators:
        sim_path = base_dir / "simulators" / sim_file
        # Run simulator without network dependency using --no-post
        proc = subprocess.run(
            [sys.executable, str(sim_path), "--no-post"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = proc.stdout.strip()
        print(f"Executed {sim_file}: Output length {len(output)} chars")

        # Parse multiple JSON objects using JSONDecoder
        decoder = json.JSONDecoder()
        pos = 0
        events_list = []
        while pos < len(output):
            idx = output.find("{", pos)
            if idx == -1:
                break
            try:
                obj, end_offset = decoder.raw_decode(output[idx:])
                events_list.append(obj)
                pos = idx + end_offset
            except Exception:
                pos = idx + 1

        assert len(events_list) >= 3, f"FAIL: Expected events for zone_1, zone_2, zone_3 in {sim_file}, got {len(events_list)}"
        for event_json in events_list:
            assert event_json["source"] == expected_src
            assert event_json["event_type"] == expected_type
            assert expected_feature in event_json["features"]
            val = event_json["features"][expected_feature]
            assert 0.0 <= val <= 1.0, f"FAIL: Feature value {val} outside 0-1"
            assert 0.80 <= event_json["confidence"] <= 0.99, f"FAIL: Confidence {event_json['confidence']} outside 0.80-0.99"
            assert event_json["timestamp"].endswith("Z"), "FAIL: Timestamp must end in Z"
            assert "event_id" not in event_json, "FAIL: Simulator must NOT generate event_id"

    print("-> TEST 7 PASSED: All 4 simulators produce valid events matching the shared contract.")

    # -------------------------------------------------------------------------
    # TEST 8: Run an anomaly command and confirm anomalous vibration_level ~0.90
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Running anomaly command: python sensor_simulator.py --anomaly --zone zone_2 ...")
    sensor_sim_path = base_dir / "simulators" / "sensor_simulator.py"
    proc = subprocess.run(
        [sys.executable, str(sensor_sim_path), "--anomaly", "--zone", "zone_2", "--no-post"],
        capture_output=True,
        text=True,
        check=True,
    )
    output = proc.stdout.strip()
    print("Anomaly Command Output:\n" + output)

    anomaly_event = json.loads(output)
    assert anomaly_event["source"] == "sensor"
    assert anomaly_event["zone"] == "zone_2"
    assert anomaly_event["event_type"] == "vibration"
    assert "vibration_level" in anomaly_event["features"]
    vibe_val = anomaly_event["features"]["vibration_level"]
    print(f"Detected anomalous vibration_level: {vibe_val}")
    assert abs(vibe_val - 0.90) < 0.05, f"FAIL: Expected vibration_level around 0.90, got {vibe_val}"
    assert "event_id" not in anomaly_event
    print("-> TEST 8 PASSED: sensor_simulator.py --anomaly --zone zone_2 produced anomalous vibration_level around 0.90.")

    # -------------------------------------------------------------------------
    # TEST 9: Run the seed script and confirm enough events for all 12 combinations
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Running seed script and verifying baseline coverage...")
    seed_path = base_dir / "db" / "seed.py"
    proc = subprocess.run(
        [sys.executable, str(seed_path), "--count", "40", "--clear", "--path", str(test_db_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    print("Seed Output:\n" + proc.stdout.strip())

    with get_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT source, zone, COUNT(*) FROM events GROUP BY source, zone")
        group_counts = cursor.fetchall()

    print(f"Discovered groups: {len(group_counts)}")
    assert len(group_counts) == 12, f"FAIL: Expected 12 source+zone combinations, found {len(group_counts)}"

    for row in group_counts:
        src, zn, cnt = row[0], row[1], row[2]
        print(f"  Group ({src:9s}, {zn:6s}) -> {cnt} events")
        assert cnt >= 30, f"FAIL: Group ({src}, {zn}) has only {cnt} events (< 30 required by Person 2)"

    print("-> TEST 9 PASSED: Seed script created >= 30 events for all 12 source + zone combinations.")

    # Clean up test db if possible
    try:
        if test_db_path.exists():
            test_db_path.unlink()
    except Exception:
        pass
    if "SITUATIONAL_DB_PATH" in os.environ:
        del os.environ["SITUATIONAL_DB_PATH"]

    print("\n" + "=" * 70)
    print("ALL 9 TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
