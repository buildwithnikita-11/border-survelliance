"""
prioritizer.py - Alert prioritization and scoring for border surveillance AI engine.

Calculates alert scores (0 to 10) and orders alerts by priority per shared/schema.md (sections 7, 10).
"""

from pathlib import Path
import random
import sys

# Ensure ai-engine directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Scoring constants from Section 10
MAX_SCORE = 10
MAX_DEVIATION_IN_SCORE = 6
SINGLE_SOURCE_MAX_SCORE = 4
POINTS_PER_SOURCE = 2


def calculate_score(alert: dict) -> float:
    """
    Calculate alert score (0 to 10) according to Section 10 rule:
    Score = min(10, 2 x number_of_sources + min(average_deviation, 6))
    For single_source alerts, score is capped at 4.
    If evidence is empty, return 0.0.
    """
    evidence = alert.get("evidence", [])
    if not evidence:
        return 0.0

    number_of_sources = len(evidence)
    deviations = [e.get("deviation", 0.0) for e in evidence]
    average_deviation = sum(deviations) / len(deviations)

    raw_score = (
        POINTS_PER_SOURCE * number_of_sources
        + min(average_deviation, MAX_DEVIATION_IN_SCORE)
    )
    score = min(float(MAX_SCORE), raw_score)

    if alert.get("type") == "single_source":
        score = min(float(SINGLE_SOURCE_MAX_SCORE), score)

    return round(score, 1)


def prioritize(alerts: list[dict]) -> list[dict]:
    """
    Return NEW alert dictionaries where 'score' is calculated with calculate_score.
    Sort by score descending, breaking ties with later time_window_start first.
    Does not modify the input list or input dictionaries.
    """
    scored_alerts = []
    for a in alerts:
        new_alert = dict(a)
        new_alert["score"] = calculate_score(a)
        scored_alerts.append(new_alert)

    # Sort: highest score first, then later time_window_start first
    scored_alerts.sort(
        key=lambda a: (a["score"], a.get("time_window_start", "")),
        reverse=True
    )
    return scored_alerts


if __name__ == "__main__":
    from anomaly_detector import find_anomalies
    from correlator import correlate
    from fake_data import make_test_scenario

    print("=" * 60)
    print("RUNNING PRIORITIZER TESTS")
    print("=" * 60)

    # -------------------------------------------------------------
    # Test 1: Prioritize scenario alerts and compare planted alerts
    # -------------------------------------------------------------
    print("\n--- Test 1: Prioritize alerts from test scenario ---")
    random.seed(3)
    scenario = make_test_scenario()
    anomalies = find_anomalies(scenario, scenario)
    raw_alerts = correlate(anomalies, now="2100-01-01T00:00:00Z")
    prioritized_alerts = prioritize(raw_alerts)

    print(f"Total prioritized alerts: {len(prioritized_alerts)}")
    for i, al in enumerate(prioritized_alerts, start=1):
        sources = [e["source"] for e in al["evidence"]]
        print(f"  #{i} [{al['type']:13s}] Zone: {al['zone']:6s} Score: {al['score']:4.1f} Start: {al['time_window_start']} Sources: {sources}")

    z2_multi = next(
        (a for a in prioritized_alerts
         if a["zone"] == "zone_2" and a["type"] == "multi_source" and {"sensor", "camera"}.issubset({e["source"] for e in a["evidence"]})),
        None
    )
    z3_single = next(
        (a for a in prioritized_alerts
         if a["zone"] == "zone_3" and a["type"] == "single_source" and "wifi" in {e["source"] for e in a["evidence"]}),
        None
    )

    if z2_multi is None:
        print("Result: FAIL - Missing zone_2 multi_source alert")
        sys.exit(1)
    if z3_single is None:
        print("Result: FAIL - Missing zone_3 single_source alert")
        sys.exit(1)

    print(f"\n  Planted zone_2 multi_source score: {z2_multi['score']}")
    print(f"  Planted zone_3 single_source score: {z3_single['score']}")

    if z2_multi["score"] <= z3_single["score"]:
        print(f"Result: FAIL - zone_2 multi_source score ({z2_multi['score']}) is not higher than zone_3 single_source score ({z3_single['score']})")
        sys.exit(1)
    else:
        print("Result: PASS - zone_2 multi_source scores higher than zone_3 single_source")

    # -------------------------------------------------------------
    # Test 2: single_source alert with high deviation (10) caps at 4.0
    # -------------------------------------------------------------
    print("\n--- Test 2: single_source with deviation 10 capped at 4.0 ---")
    mock_single_high = {
        "type": "single_source",
        "evidence": [{"source": "sensor", "deviation": 10.0}],
    }
    score_t2 = calculate_score(mock_single_high)
    if score_t2 == 4.0:
        print(f"Result: PASS - Single source score is {score_t2} (capped at 4.0)")
    else:
        print(f"Result: FAIL - Expected 4.0, got {score_t2}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 3: multi_source with 2 sources and avg deviation 6 -> 10.0
    # -------------------------------------------------------------
    print("\n--- Test 3: multi_source (2 sources, avg deviation 6) = 10.0 ---")
    mock_multi_10 = {
        "type": "multi_source",
        "evidence": [
            {"source": "sensor", "deviation": 6.0},
            {"source": "camera", "deviation": 6.0},
        ],
    }
    score_t3 = calculate_score(mock_multi_10)
    if score_t3 == 10.0:
        print(f"Result: PASS - Multi source score is exactly {score_t3}")
    else:
        print(f"Result: FAIL - Expected 10.0, got {score_t3}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 4: multi_source with avg deviation 20 is still 10.0 (capped)
    # -------------------------------------------------------------
    print("\n--- Test 4: multi_source (2 sources, avg deviation 20) = 10.0 (capped) ---")
    mock_multi_20 = {
        "type": "multi_source",
        "evidence": [
            {"source": "sensor", "deviation": 20.0},
            {"source": "camera", "deviation": 20.0},
        ],
    }
    score_t4 = calculate_score(mock_multi_20)
    if score_t4 == 10.0:
        print(f"Result: PASS - Multi source score with deviation 20 is capped at {score_t4}")
    else:
        print(f"Result: FAIL - Expected 10.0, got {score_t4}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 5: multi_source with 3 sources scores higher than 2 sources
    # -------------------------------------------------------------
    print("\n--- Test 5: 3 sources scores higher than 2 sources ---")
    mock_2_sources = {
        "type": "multi_source",
        "evidence": [
            {"source": "sensor", "deviation": 3.0},
            {"source": "camera", "deviation": 3.0},
        ],
    }
    mock_3_sources = {
        "type": "multi_source",
        "evidence": [
            {"source": "sensor", "deviation": 3.0},
            {"source": "camera", "deviation": 3.0},
            {"source": "wifi", "deviation": 3.0},
        ],
    }
    score_2s = calculate_score(mock_2_sources)
    score_3s = calculate_score(mock_3_sources)
    print(f"  2 sources score: {score_2s}, 3 sources score: {score_3s}")
    if score_3s > score_2s:
        print("Result: PASS - 3 sources scores higher than 2 sources")
    else:
        print(f"Result: FAIL - Expected score_3s ({score_3s}) > score_2s ({score_2s})")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 6: prioritize does not mutate input and preserves all 10 keys
    # -------------------------------------------------------------
    print("\n--- Test 6: Immuntability and exact 10 keys preserved ---")
    original_input = [
        {
            "alert_id": None,
            "type": "single_source",
            "zone": "zone_1",
            "created_at": "2026-09-28T12:05:00Z",
            "time_window_start": "2026-09-28T12:00:00Z",
            "time_window_end": "2026-09-28T12:03:00Z",
            "score": 0.0,
            "evidence": [{"source": "sensor", "deviation": 4.0}],
            "status": "pending",
            "analyst_note": "",
        }
    ]
    expected_keys = {
        "alert_id",
        "type",
        "zone",
        "created_at",
        "time_window_start",
        "time_window_end",
        "score",
        "evidence",
        "status",
        "analyst_note",
    }
    result_alerts = prioritize(original_input)

    # Check input was not modified
    input_mutated = (original_input[0]["score"] != 0.0) or (result_alerts[0] is original_input[0])
    keys_match = (set(result_alerts[0].keys()) == expected_keys)

    if not input_mutated and keys_match:
        print("Result: PASS - Input list not mutated and all 10 schema keys preserved")
    else:
        print(f"Result: FAIL - input_mutated: {input_mutated}, keys_match: {keys_match}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 7: Equal scores tie-broken by later time_window_start first
    # -------------------------------------------------------------
    print("\n--- Test 7: Equal scores broken by later time_window_start first ---")
    alert_early = {
        "alert_id": "early",
        "type": "single_source",
        "zone": "zone_1",
        "created_at": "2026-09-28T12:05:00Z",
        "time_window_start": "2026-09-28T12:00:00Z",
        "time_window_end": "2026-09-28T12:03:00Z",
        "score": 0.0,
        "evidence": [{"source": "sensor", "deviation": 5.0}],
        "status": "pending",
        "analyst_note": "",
    }
    alert_late = {
        "alert_id": "late",
        "type": "single_source",
        "zone": "zone_2",
        "created_at": "2026-09-28T12:15:00Z",
        "time_window_start": "2026-09-28T12:10:00Z",
        "time_window_end": "2026-09-28T12:13:00Z",
        "score": 0.0,
        "evidence": [{"source": "sensor", "deviation": 5.0}],
        "status": "pending",
        "analyst_note": "",
    }

    # Pass in both orders to verify sorting is strictly by timestamp descending
    order_a = prioritize([alert_early, alert_late])
    order_b = prioritize([alert_late, alert_early])

    if order_a[0]["alert_id"] == "late" and order_b[0]["alert_id"] == "late":
        print(f"Result: PASS - Later alert ({order_a[0]['time_window_start']}) ordered before earlier alert ({order_a[1]['time_window_start']})")
    else:
        print(f"Result: FAIL - Incorrect ordering for equal scores: {[a['alert_id'] for a in order_a]}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL 7 TESTS PASSED")
    print("=" * 60)
