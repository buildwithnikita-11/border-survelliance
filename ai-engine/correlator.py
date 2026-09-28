"""
correlator.py - Anomaly correlator for border surveillance AI engine.

Groups anomalies occurring within the 3-minute correlation window in the same zone
and produces multi-source and single-source alerts per shared/schema.md (sections 3, 7, 10).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys

# Ensure ai-engine directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Fixed correlation window from Section 10 (3 minutes)
CORRELATION_WINDOW_SECONDS = 180


def parse_iso_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 UTC timestamp string ending in Z to timezone-aware UTC datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def format_iso_timestamp(dt: datetime) -> str:
    """Format timezone-aware datetime into UTC ISO 8601 string ending in Z."""
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def group_anomalies(anomalies: list[dict]) -> list[list[dict]]:
    """
    Group anomalies by zone and correlation window.

    - Splits anomalies by zone (never mix zones).
    - Sorts chronologically within each zone.
    - Forms a group starting with the earliest ungrouped anomaly and adds all
      anomalies occurring within CORRELATION_WINDOW_SECONDS of that first anomaly.
    - The next anomaly after that window starts a new group.
    - Returns a list of anomaly groups.
    """
    # Collect unique zones in sorted order
    zones_present = sorted(list({a["zone"] for a in anomalies if a.get("zone")}))

    groups: list[list[dict]] = []

    for zone in zones_present:
        zone_anomalies = [a for a in anomalies if a.get("zone") == zone]
        zone_anomalies.sort(key=lambda a: parse_iso_timestamp(a["timestamp"]))

        current_group: list[dict] = []
        group_start_dt: datetime | None = None

        for a in zone_anomalies:
            a_dt = parse_iso_timestamp(a["timestamp"])
            if not current_group:
                current_group = [a]
                group_start_dt = a_dt
            elif group_start_dt is not None and (a_dt - group_start_dt).total_seconds() <= CORRELATION_WINDOW_SECONDS:
                current_group.append(a)
            else:
                groups.append(current_group)
                current_group = [a]
                group_start_dt = a_dt

        if current_group:
            groups.append(current_group)

    return groups


def build_alert(group: list[dict], created_at: str) -> dict:
    """
    Build an alert dictionary in the exact format of shared/schema.md section 7.

    - alert_id: None (engine_runner.py creates the real id).
    - type: 'multi_source' if 2+ different sources, otherwise 'single_source'.
    - zone: Zone of the group.
    - created_at: ISO timestamp when alert was generated.
    - time_window_start: Timestamp of the first anomaly in the group.
    - time_window_end: time_window_start plus CORRELATION_WINDOW_SECONDS.
    - score: 0.0 (prioritizer.py sets the real score).
    - status: 'pending', analyst_note: ''.
    - evidence: ONE entry per source (highest deviation kept), sorted by deviation desc.
      Does NOT include zone or timestamp.
    """
    first_anomaly = group[0]
    zone = first_anomaly["zone"]
    time_window_start = first_anomaly["timestamp"]

    start_dt = parse_iso_timestamp(time_window_start)
    end_dt = start_dt + timedelta(seconds=CORRELATION_WINDOW_SECONDS)
    time_window_end = format_iso_timestamp(end_dt)

    # Determine alert type: multi_source if 2 or more different sources
    unique_sources = {a["source"] for a in group}
    alert_type = "multi_source" if len(unique_sources) >= 2 else "single_source"

    # Evidence: keep only the anomaly with the highest deviation per source
    best_per_source: dict[str, dict] = {}
    for a in group:
        src = a["source"]
        if src not in best_per_source or a["deviation"] > best_per_source[src]["deviation"]:
            best_per_source[src] = a

    evidence = []
    for a in best_per_source.values():
        evidence.append({
            "event_id": a["event_id"],
            "source": a["source"],
            "main_feature": a["main_feature"],
            "value": a["value"],
            "normal_average": a["normal_average"],
            "deviation": a["deviation"],
            "confidence": a["confidence"],
            "reason": a["reason"],
        })

    # Sort evidence by deviation, highest first
    evidence.sort(key=lambda e: e["deviation"], reverse=True)

    # Return exactly the 10 keys required by schema.md section 7
    return {
        "alert_id": None,  # engine_runner.py creates the real id
        "type": alert_type,
        "zone": zone,
        "created_at": created_at,
        "time_window_start": time_window_start,
        "time_window_end": time_window_end,
        "score": 0.0,  # prioritizer.py sets the real score
        "evidence": evidence,
        "status": "pending",
        "analyst_note": "",
    }


def correlate(anomalies: list[dict], now: str | None = None) -> list[dict]:
    """
    Group anomalies and turn them into alerts.

    - 'now' is an ISO timestamp string. If None, current UTC time is used.
    - multi_source alerts are always returned.
    - single_source alerts are returned ONLY if the correlation window has closed
      (now is later than time_window_end).
    - Returns alerts sorted by time_window_start.
    """
    if now is None:
        now_dt = datetime.now(timezone.utc).replace(microsecond=0)
        now_str = format_iso_timestamp(now_dt)
    else:
        now_str = now
        now_dt = parse_iso_timestamp(now)

    groups = group_anomalies(anomalies)

    alerts = []
    for group in groups:
        alert = build_alert(group, created_at=now_str)
        if alert["type"] == "multi_source":
            # Multi-source alerts are immediately confirmed
            alerts.append(alert)
        elif alert["type"] == "single_source":
            # Single-source alerts are only returned once the window has closed
            window_end_dt = parse_iso_timestamp(alert["time_window_end"])
            if now_dt > window_end_dt:
                alerts.append(alert)

    # Return alerts sorted by time_window_start
    alerts.sort(key=lambda a: parse_iso_timestamp(a["time_window_start"]))
    return alerts


if __name__ == "__main__":
    from anomaly_detector import find_anomalies
    from fake_data import make_test_scenario

    print("=" * 60)
    print("RUNNING CORRELATOR TESTS")
    print("=" * 60)

    # Helper for creating mock anomalies
    def make_mock(source: str, zone: str, ts: str, dev: float = 4.0, eid: str = "evt_mock"):
        return {
            "event_id": eid,
            "source": source,
            "zone": zone,
            "timestamp": ts,
            "main_feature": "vibration_level" if source == "sensor" else "movement_level" if source == "camera" else "signal_change",
            "value": 0.85,
            "normal_average": 0.20 if source == "sensor" else 0.15,
            "deviation": dev,
            "confidence": 0.90,
            "reason": f"{source} is far above normal for {zone}",
        }

    # -------------------------------------------------------------
    # Test 1: Scenario with closed windows produces planted alerts
    # -------------------------------------------------------------
    print("\n--- Test 1: Test scenario planted alerts (all windows closed) ---")
    random.seed(3)
    scenario = make_test_scenario()
    detected_anomalies = find_anomalies(scenario, scenario)
    print(f"Total anomalies from scenario: {len(detected_anomalies)}")

    alerts_all_closed = correlate(detected_anomalies, now="2100-01-01T00:00:00Z")
    print(f"Total alerts generated: {len(alerts_all_closed)}")

    z2_multi = next(
        (a for a in alerts_all_closed
         if a["zone"] == "zone_2" and a["type"] == "multi_source" and {"sensor", "camera"}.issubset({e["source"] for e in a["evidence"]})),
        None
    )
    z3_single = next(
        (a for a in alerts_all_closed
         if a["zone"] == "zone_3" and a["type"] == "single_source" and "wifi" in {e["source"] for e in a["evidence"]}),
        None
    )

    if z2_multi is None:
        print("Result: FAIL - Missing multi_source alert in zone_2 with sensor and camera")
        sys.exit(1)
    if z3_single is None:
        print("Result: FAIL - Missing single_source alert in zone_3 with wifi")
        sys.exit(1)

    print("Result: PASS - Found planted alerts:")
    print(f"  - zone_2 multi_source: start={z2_multi['time_window_start']}, sources={[e['source'] for e in z2_multi['evidence']]}")
    print(f"  - zone_3 single_source: start={z3_single['time_window_start']}, sources={[e['source'] for e in z3_single['evidence']]}")

    # -------------------------------------------------------------
    # Test 2: Other alerts (random false alarms)
    # -------------------------------------------------------------
    print("\n--- Test 2: Other alerts from false alarms ---")
    other_alerts = [
        a for a in alerts_all_closed
        if a is not z2_multi and a is not z3_single
    ]
    print(f"Other alerts generated: {len(other_alerts)}")
    for a in other_alerts:
        srcs = [e["source"] for e in a["evidence"]]
        print(f"  - {a['type']} in {a['zone']} (start: {a['time_window_start']}, sources: {srcs})")
    print("Result: PASS")

    # -------------------------------------------------------------
    # Test 3: Two anomalies 5 minutes apart in same zone -> 2 single_source
    # -------------------------------------------------------------
    print("\n--- Test 3: Two anomalies 5 minutes apart in same zone ---")
    ano_3a = make_mock("camera", "zone_1", "2026-09-28T12:00:00Z", eid="evt_3a")
    ano_3b = make_mock("sensor", "zone_1", "2026-09-28T12:05:00Z", eid="evt_3b")
    alerts_t3 = correlate([ano_3a, ano_3b], now="2026-09-28T12:15:00Z")

    types_t3 = [a["type"] for a in alerts_t3]
    if len(alerts_t3) == 2 and types_t3 == ["single_source", "single_source"]:
        print("Result: PASS - Produced exactly two single_source alerts, no multi_source")
    else:
        print(f"Result: FAIL - Expected 2 single_source alerts, got {types_t3}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 4: Anomalies in different zones must NOT merge
    # -------------------------------------------------------------
    print("\n--- Test 4: Anomalies 60s apart in DIFFERENT zones ---")
    ano_4a = make_mock("camera", "zone_1", "2026-09-28T12:00:00Z", eid="evt_4a")
    ano_4b = make_mock("sensor", "zone_2", "2026-09-28T12:01:00Z", eid="evt_4b")
    alerts_t4 = correlate([ano_4a, ano_4b], now="2026-09-28T12:15:00Z")

    if len(alerts_t4) == 2 and all(a["type"] == "single_source" for a in alerts_t4):
        zones_t4 = {a["zone"] for a in alerts_t4}
        if zones_t4 == {"zone_1", "zone_2"}:
            print("Result: PASS - Separated by zone into two distinct single_source alerts")
        else:
            print(f"Result: FAIL - Unexpected zones: {zones_t4}")
            sys.exit(1)
    else:
        print(f"Result: FAIL - Expected 2 single_source alerts across zones, got {alerts_t4}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 5: Three same-source anomalies in same zone -> 1 alert, 1 evidence (highest dev)
    # -------------------------------------------------------------
    print("\n--- Test 5: Three same-source anomalies in same zone ---")
    ano_5a = make_mock("sensor", "zone_1", "2026-09-28T12:00:00Z", dev=4.0, eid="evt_5a")
    ano_5b = make_mock("sensor", "zone_1", "2026-09-28T12:00:20Z", dev=7.5, eid="evt_5b")
    ano_5c = make_mock("sensor", "zone_1", "2026-09-28T12:00:40Z", dev=5.2, eid="evt_5c")
    alerts_t5 = correlate([ano_5a, ano_5b, ano_5c], now="2026-09-28T12:15:00Z")

    if len(alerts_t5) == 1:
        alert_5 = alerts_t5[0]
        if alert_5["type"] == "single_source" and len(alert_5["evidence"]) == 1:
            dev_kept = alert_5["evidence"][0]["deviation"]
            eid_kept = alert_5["evidence"][0]["event_id"]
            if dev_kept == 7.5 and eid_kept == "evt_5b":
                print(f"Result: PASS - Kept single evidence entry with highest deviation ({dev_kept})")
            else:
                print(f"Result: FAIL - Expected dev 7.5 (evt_5b), got {dev_kept} ({eid_kept})")
                sys.exit(1)
        else:
            print(f"Result: FAIL - Expected single_source with 1 evidence entry, got {alert_5}")
            sys.exit(1)
    else:
        print(f"Result: FAIL - Expected 1 alert, got {len(alerts_t5)}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 6: Single anomaly with open window returns no alert
    # -------------------------------------------------------------
    print("\n--- Test 6: Single anomaly with open window (30s after) ---")
    ano_6 = make_mock("sensor", "zone_1", "2026-09-28T12:00:00Z", eid="evt_6")
    alerts_t6 = correlate([ano_6], now="2026-09-28T12:00:30Z")
    if len(alerts_t6) == 0:
        print("Result: PASS - No alert returned while correlation window is still open")
    else:
        print(f"Result: FAIL - Expected 0 alerts, got {len(alerts_t6)}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 7: Multi-source pair with open window IS returned
    # -------------------------------------------------------------
    print("\n--- Test 7: Multi-source pair with open window IS returned ---")
    ano_7a = make_mock("sensor", "zone_2", "2026-09-28T12:00:00Z", eid="evt_7a")
    ano_7b = make_mock("camera", "zone_2", "2026-09-28T12:00:30Z", eid="evt_7b")
    alerts_t7 = correlate([ano_7a, ano_7b], now="2026-09-28T12:00:45Z")
    if len(alerts_t7) == 1 and alerts_t7[0]["type"] == "multi_source":
        print("Result: PASS - Multi-source alert returned immediately despite open window")
    else:
        print(f"Result: FAIL - Expected 1 multi_source alert, got {alerts_t7}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Test 8: Schema compliance (exact 10 keys, exact 8 evidence keys, end > start)
    # -------------------------------------------------------------
    print("\n--- Test 8: Verify exact schema keys and window validity ---")
    expected_alert_keys = {
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
    expected_evidence_keys = {
        "event_id",
        "source",
        "main_feature",
        "value",
        "normal_average",
        "deviation",
        "confidence",
        "reason",
    }

    test8_passed = True
    all_tested_alerts = alerts_all_closed + alerts_t3 + alerts_t4 + alerts_t5 + alerts_t7
    for al in all_tested_alerts:
        if set(al.keys()) != expected_alert_keys:
            print(f"FAIL: Alert keys mismatch: {set(al.keys())} != {expected_alert_keys}")
            test8_passed = False
            break

        start_time = parse_iso_timestamp(al["time_window_start"])
        end_time = parse_iso_timestamp(al["time_window_end"])
        if end_time <= start_time:
            print(f"FAIL: time_window_end ({al['time_window_end']}) not later than start ({al['time_window_start']})")
            test8_passed = False
            break

        for ev in al["evidence"]:
            if set(ev.keys()) != expected_evidence_keys:
                print(f"FAIL: Evidence keys mismatch: {set(ev.keys())} != {expected_evidence_keys}")
                test8_passed = False
                break

    if test8_passed:
        print(f"Result: PASS - All {len(all_tested_alerts)} alerts strictly match schema (10 alert keys, 8 evidence keys, end > start)")
    else:
        print("Result: FAIL")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL 8 TESTS PASSED")
    print("=" * 60)
