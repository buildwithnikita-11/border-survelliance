"""
baseline.py - Baseline calculation for border surveillance AI engine.

Calculates normal averages and standard deviations for each source + zone pair
according to shared/schema.md (sections 3, 5, 6, 10, 11).
"""

import math
from pathlib import Path
import statistics
import sys

# Fixed lists from Section 3
SOURCES = ["camera", "wifi", "sensor", "satellite"]
ZONES = ["zone_1", "zone_2", "zone_3"]

# Main feature per source from Section 5
MAIN_FEATURE = {
    "camera": "movement_level",
    "sensor": "vibration_level",
    "wifi": "signal_change",
    "satellite": "surface_change",
}

# Normal average reference values from Section 11
NORMAL_AVERAGES = {
    "camera": 0.15,
    "sensor": 0.20,
    "wifi": 0.15,
    "satellite": 0.10,
}


def get_baseline(events: list[dict], source: str, zone: str, before: str | None = None) -> dict | None:
    """
    Work out what 'normal' looks like for a specific source + zone.

    - Filters by source and zone.
    - Ignores events with confidence below 0.5 (section 6).
    - Ignores events missing the main feature for that source.
    - If 'before' ISO timestamp is given, keeps only events strictly earlier than 'before'.
    - Takes the last 200 events after sorting by timestamp (section 10).
    - Returns None if fewer than 30 events are left (section 10).
    - If std < 0.01, clamps std to 0.01 to prevent division by zero in later scoring.
    """
    main_feature = MAIN_FEATURE.get(source)
    if not main_feature:
        return None

    filtered_events = []
    for e in events:
        # Match source and zone
        if e.get("source") != source or e.get("zone") != zone:
            continue

        # Ignore events with confidence below 0.5 (section 6)
        confidence = e.get("confidence", 0)
        if confidence < 0.5:
            continue

        # Ignore events that do not contain the main feature
        features = e.get("features", {})
        if main_feature not in features or features[main_feature] is None:
            continue

        # If before is given, keep only events strictly earlier than 'before'
        if before is not None and e.get("timestamp", "") >= before:
            continue

        filtered_events.append(e)

    # Sort by timestamp and take the last 200 events (section 10)
    filtered_events.sort(key=lambda x: x.get("timestamp", ""))
    selected_events = filtered_events[-200:]

    # Engine requires at least 30 events before judging (section 10)
    if len(selected_events) < 30:
        return None

    values = [e["features"][main_feature] for e in selected_events]
    avg = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0

    # Prevent division by zero later in anomaly scoring by setting minimum std to 0.01
    if std < 0.01:
        std = 0.01

    return {
        "source": source,
        "zone": zone,
        "average": round(avg, 4),
        "std": round(std, 4),
        "count": len(selected_events),
    }


def build_all_baselines(events: list[dict], before: str | None = None) -> dict[tuple[str, str], dict | None]:
    """
    Call get_baseline for every source + zone combination (4 sources x 3 zones).
    Returns dictionary keyed by (source, zone), including None results.
    """
    baselines = {}
    for source in SOURCES:
        for zone in ZONES:
            baselines[(source, zone)] = get_baseline(events, source, zone, before=before)
    return baselines


if __name__ == "__main__":
    # Ensure local directory is importable
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fake_data import make_normal_data, make_test_scenario

    print("=" * 60)
    print("RUNNING BASELINE TESTS")
    print("=" * 60)

    # -------------------------------------------------------------
    # Test 1: Build baselines from make_normal_data() and check averages
    # -------------------------------------------------------------
    print("\n--- Test 1: Build baselines from make_normal_data() ---")
    normal_data = make_normal_data()
    all_baselines = build_all_baselines(normal_data)

    test1_passed = True
    for (src, zn), b in all_baselines.items():
        if b is None:
            print(f"FAIL: Baseline for ({src}, {zn}) is None")
            test1_passed = False
            break

        exp_avg = NORMAL_AVERAGES[src]
        diff = abs(b["average"] - exp_avg)
        print(f"  ({src:9s}, {zn:6s}) -> avg: {b['average']:.4f} (expected ~{exp_avg:.2f}), std: {b['std']:.4f}, count: {b['count']}")
        if diff > 0.05:
            print(f"FAIL: {src} in {zn} average {b['average']} deviates {diff:.4f} (> 0.05) from expected {exp_avg}")
            test1_passed = False
            break

    if test1_passed:
        print("Result: PASS - All 12 baselines within 0.05 of section 11 averages")
    else:
        print("Result: FAIL")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 2: Fewer than 30 events returns None
    # -------------------------------------------------------------
    print("\n--- Test 2: get_baseline with only 10 events ---")
    grp_events = [e for e in normal_data if e["source"] == "sensor" and e["zone"] == "zone_1"][:10]
    b_small = get_baseline(grp_events, "sensor", "zone_1")
    if b_small is None:
        print("Result: PASS - Returned None for 10 events (< 30 required)")
    else:
        print(f"Result: FAIL - Expected None, got {b_small}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 3: Low confidence (< 0.5) events do not change baseline
    # -------------------------------------------------------------
    print("\n--- Test 3: Low confidence (< 0.5) events ignored ---")
    b_before = get_baseline(normal_data, "sensor", "zone_1")
    noisy_data = [dict(e) for e in normal_data]
    # Add several low-confidence events with extreme values
    for i in range(10):
        noisy_data.append({
            "event_id": f"evt_noise_{i}",
            "source": "sensor",
            "zone": "zone_1",
            "timestamp": normal_data[-1]["timestamp"],
            "event_type": "vibration",
            "features": {"vibration_level": 1.0},
            "confidence": 0.3,
        })
    b_after = get_baseline(noisy_data, "sensor", "zone_1")
    if b_before == b_after:
        print(f"Result: PASS - Low confidence events ignored (avg before: {b_before['average']}, avg after: {b_after['average']})")
    else:
        print(f"Result: FAIL - Baseline changed! Before: {b_before}, After: {b_after}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 4: make_test_scenario() with before = anomaly timestamp
    # -------------------------------------------------------------
    print("\n--- Test 4: Baseline with 'before' excludes planted anomaly ---")
    scenario_events = make_test_scenario()

    # Find the planted sensor anomaly in zone_2 (vibration_level > 0.5)
    planted_sensor_anomaly = next(
        e for e in scenario_events
        if e["source"] == "sensor" and e["zone"] == "zone_2" and e["features"].get("vibration_level", 0) > 0.5
    )
    anomaly_timestamp = planted_sensor_anomaly["timestamp"]
    print(f"  Planted zone_2 sensor anomaly timestamp: {anomaly_timestamp} (val: {planted_sensor_anomaly['features']['vibration_level']})")

    # Baseline before the anomaly
    b_clean = get_baseline(scenario_events, "sensor", "zone_2", before=anomaly_timestamp)
    if b_clean is not None and abs(b_clean["average"] - 0.20) <= 0.05:
        print(f"Result: PASS - zone_2 sensor baseline before anomaly is {b_clean['average']:.4f} (close to 0.20, anomaly excluded)")
    else:
        print(f"Result: FAIL - Unexpected baseline: {b_clean}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL 4 TESTS PASSED")
    print("=" * 60)
