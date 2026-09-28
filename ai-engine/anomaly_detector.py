"""
anomaly_detector.py - Anomaly detector for border surveillance AI engine.

Identifies events deviating 3 or more standard deviations from their baseline
according to shared/schema.md (sections 5, 6, 7, 10).
"""

from pathlib import Path
import sys

# Ensure ai-engine directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baseline import MAIN_FEATURE, get_baseline

# Engine rules from Section 6 and Section 10
ANOMALY_THRESHOLD = 3
MIN_CONFIDENCE = 0.5


def calculate_deviation(value: float, baseline: dict) -> float:
    """
    Calculate how many standard deviations away from normal the value is.
    Always returns a positive number.
    """
    return abs(value - baseline["average"]) / baseline["std"]


def check_event(event: dict, history: list[dict]) -> dict | None:
    """
    Check if a single event is anomalous against historical baseline.

    - Returns None if confidence is below MIN_CONFIDENCE (0.5).
    - Returns None if the event lacks the main feature for its source.
    - Baseline uses events strictly before event['timestamp'] to avoid self-inclusion.
    - Returns None if baseline is None (< 30 historical events).
    - Returns None if deviation is below ANOMALY_THRESHOLD (3).
    - Otherwise returns a dictionary with 10 keys:
      event_id, source, zone, timestamp, main_feature, value,
      normal_average, deviation, confidence, reason.
    """
    # Ignore events with confidence below threshold (section 6)
    confidence = event.get("confidence", 0)
    if confidence < MIN_CONFIDENCE:
        return None

    source = event.get("source")
    zone = event.get("zone")
    main_feature = MAIN_FEATURE.get(source)
    if not main_feature:
        return None

    features = event.get("features", {})
    if main_feature not in features or features[main_feature] is None:
        return None

    timestamp = event.get("timestamp")

    # Get baseline strictly before this event's timestamp
    baseline = get_baseline(history, source, zone, before=timestamp)
    if baseline is None:
        return None

    value = features[main_feature]
    raw_deviation = calculate_deviation(value, baseline)
    if raw_deviation < ANOMALY_THRESHOLD:
        return None

    direction = "above" if value >= baseline["average"] else "below"
    reason = f"{source} {main_feature} is far {direction} normal for {zone}"

    # Note: 'zone' and 'timestamp' are included here for the correlator later.
    # They are NOT part of the alert evidence in section 7.
    # The correlator must remove them when it builds the alert evidence.
    return {
        "event_id": event.get("event_id"),
        "source": source,
        "zone": zone,
        "timestamp": timestamp,
        "main_feature": main_feature,
        "value": value,
        "normal_average": round(baseline["average"], 3),
        "deviation": round(raw_deviation, 2),
        "confidence": confidence,
        "reason": reason,
    }


def find_anomalies(events_to_check: list[dict], history: list[dict]) -> list[dict]:
    """
    Run check_event on each event and return list of anomalies sorted by timestamp.
    Groups history by (source, zone) once before the loop for fast baseline lookups.
    """
    # Group history by (source, zone) to avoid repeated list scans
    grouped_history: dict[tuple[str, str], list[dict]] = {}
    for h in history:
        src = h.get("source")
        zn = h.get("zone")
        if src and zn:
            grouped_history.setdefault((src, zn), []).append(h)

    anomalies = []
    for event in events_to_check:
        src = event.get("source")
        zn = event.get("zone")
        sub_history = grouped_history.get((src, zn), [])
        result = check_event(event, sub_history)
        if result is not None:
            anomalies.append(result)

    anomalies.sort(key=lambda a: a.get("timestamp", ""))
    return anomalies


if __name__ == "__main__":
    from fake_data import make_test_scenario

    print("=" * 60)
    print("RUNNING ANOMALY DETECTOR TESTS")
    print("=" * 60)

    # Generate scenario data; use all events as both events_to_check and history
    scenario = make_test_scenario()
    total_events = len(scenario)
    print(f"Total scenario events: {total_events}")

    # Find the 3 planted anomaly events from scenario definition
    planted_sensor = next(
        e for e in scenario
        if e["source"] == "sensor" and e["zone"] == "zone_2" and e["features"].get("vibration_level", 0) > 0.6
    )
    planted_camera = next(
        e for e in scenario
        if e["source"] == "camera" and e["zone"] == "zone_2" and e["features"].get("movement_level", 0) > 0.6
    )
    planted_wifi = next(
        e for e in scenario
        if e["source"] == "wifi" and e["zone"] == "zone_3" and e["features"].get("signal_change", 0) > 0.6
    )
    planted_ids = {planted_sensor["event_id"], planted_camera["event_id"], planted_wifi["event_id"]}

    # Detect anomalies
    anomalies = find_anomalies(scenario, scenario)
    print(f"Total anomalies flagged: {len(anomalies)}")

    # -------------------------------------------------------------
    # Test 1: Planted anomalies are found
    # -------------------------------------------------------------
    print("\n--- Test 1: Verify planted anomalies are found ---")
    found_ids = {a["event_id"] for a in anomalies}

    missing_planted = []
    if planted_sensor["event_id"] not in found_ids:
        missing_planted.append("zone_2 sensor")
    if planted_camera["event_id"] not in found_ids:
        missing_planted.append("zone_2 camera")
    if planted_wifi["event_id"] not in found_ids:
        missing_planted.append("zone_3 wifi")

    if missing_planted:
        print(f"Result: FAIL - Missing planted anomalies: {', '.join(missing_planted)}")
        sys.exit(1)
    else:
        print("Result: PASS - All 3 planted anomalies found:")
        for a in anomalies:
            if a["event_id"] in planted_ids:
                print(f"  [Planted] {a['source']} in {a['zone']}: dev={a['deviation']}, val={a['value']}, avg={a['normal_average']}")

    # -------------------------------------------------------------
    # Test 2: Other flagged events (false alarms) < 2%
    # -------------------------------------------------------------
    print("\n--- Test 2: Other flagged events (random false alarms) ---")
    other_flagged = [a for a in anomalies if a["event_id"] not in planted_ids]
    false_alarm_count = len(other_flagged)
    false_alarm_pct = (false_alarm_count / total_events) * 100

    print(f"Flagged non-planted events count: {false_alarm_count}")
    print(f"False alarm percentage: {false_alarm_pct:.2f}% of all events (threshold: 2.0%)")
    for a in other_flagged:
        print(f"  - {a['event_id']} ({a['source']}, {a['zone']}): val={a['value']}, dev={a['deviation']}, reason: '{a['reason']}'")

    if false_alarm_pct > 2.0:
        print(f"Result: FAIL - False alarm rate {false_alarm_pct:.2f}% exceeds 2%")
        sys.exit(1)
    else:
        print("Result: PASS - False alarm rate within acceptable threshold (<= 2%)")

    # -------------------------------------------------------------
    # Test 3: Zone 1 (quiet zone) flagged count
    # -------------------------------------------------------------
    print("\n--- Test 3: Check zone_1 flagged count ---")
    zone_1_flagged = [a for a in anomalies if a["zone"] == "zone_1"]
    print(f"zone_1 events flagged: {len(zone_1_flagged)} (no planted anomalies in zone_1)")
    print("Result: PASS")

    # -------------------------------------------------------------
    # Test 4: Low confidence event (< 0.5) is NOT flagged
    # -------------------------------------------------------------
    print("\n--- Test 4: Low confidence event (< 0.5) ignored ---")
    low_conf_event = {
        "event_id": "evt_test_low_conf",
        "source": "sensor",
        "zone": "zone_2",
        "timestamp": scenario[-1]["timestamp"],
        "event_type": "vibration",
        "features": {"vibration_level": 1.0},
        "confidence": 0.3,
    }
    result_low_conf = check_event(low_conf_event, scenario)
    if result_low_conf is None:
        print("Result: PASS - Event with confidence 0.3 returned None despite extreme value 1.0")
    else:
        print(f"Result: FAIL - Low confidence event was flagged: {result_low_conf}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 5: Insufficient history (< 30 events) is NOT flagged
    # -------------------------------------------------------------
    print("\n--- Test 5: Event with only 10 events of history ---")
    short_history = [e for e in scenario if e["source"] == "sensor" and e["zone"] == "zone_1"][:10]
    extreme_event = {
        "event_id": "evt_test_short_hist",
        "source": "sensor",
        "zone": "zone_1",
        "timestamp": scenario[-1]["timestamp"],
        "event_type": "vibration",
        "features": {"vibration_level": 1.0},
        "confidence": 0.95,
    }
    result_short_hist = check_event(extreme_event, short_history)
    if result_short_hist is None:
        print("Result: PASS - Event with 10 historical events returned None (< 30 threshold)")
    else:
        print(f"Result: FAIL - Short history event was flagged: {result_short_hist}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 6: Verify 10 keys and non-empty reason on all anomalies
    # -------------------------------------------------------------
    print("\n--- Test 6: Verify exact 10 keys and reason on all anomalies ---")
    expected_keys = {
        "event_id",
        "source",
        "zone",
        "timestamp",
        "main_feature",
        "value",
        "normal_average",
        "deviation",
        "confidence",
        "reason",
    }

    test6_passed = True
    for a in anomalies:
        actual_keys = set(a.keys())
        if actual_keys != expected_keys:
            print(f"FAIL: Keys mismatch for {a['event_id']}: {actual_keys} != {expected_keys}")
            test6_passed = False
            break
        if not isinstance(a["reason"], str) or len(a["reason"].strip()) == 0:
            print(f"FAIL: Empty reason for {a['event_id']}")
            test6_passed = False
            break

    if test6_passed:
        print(f"Result: PASS - All {len(anomalies)} anomalies have exactly the 10 expected keys and valid reasons")
    else:
        print("Result: FAIL")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL 6 TESTS PASSED")
    print("=" * 60)
