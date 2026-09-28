"""
fake_data.py - Synthetic event generator for border surveillance AI engine.

Adheres strictly to shared/schema.md (sections 3, 5, 6, 10, 11).
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random

# Fixed lists from Section 3
SOURCES = ["camera", "wifi", "sensor", "satellite"]
ZONES = ["zone_1", "zone_2", "zone_3"]

# Source configuration from Sections 5 and 11
SOURCE_CONFIG = {
    "camera": {
        "event_type": "movement",
        "main_feature": "movement_level",
        "normal_avg": 0.15,
        "spread": 0.05,
        "anomaly_val": 0.85,
    },
    "sensor": {
        "event_type": "vibration",
        "main_feature": "vibration_level",
        "normal_avg": 0.20,
        "spread": 0.05,
        "anomaly_val": 0.90,
    },
    "wifi": {
        "event_type": "signal_change",
        "main_feature": "signal_change",
        "normal_avg": 0.15,
        "spread": 0.05,
        "anomaly_val": 0.80,
    },
    "satellite": {
        "event_type": "surface_change",
        "main_feature": "surface_change",
        "normal_avg": 0.10,
        "spread": 0.05,
        "anomaly_val": 0.75,
    },
}

_event_counter = 0


def _generate_event_id() -> str:
    """Generate sequential event ID matching 'evt_001' format."""
    global _event_counter
    _event_counter += 1
    return f"evt_{_event_counter:03d}"


def _clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp float value to [min_val, max_val] range."""
    return max(min_val, min(max_val, val))


def make_normal_data(count_per_group: int = 200, end_time: datetime | None = None) -> list[dict]:
    """
    Generate normal events for all 4 sources and 3 zones.

    One group = one source + one zone.
    Timestamps go forward, 5 seconds apart, ending at current time, with 'Z'.
    Event ID looks like 'evt_001'.
    Confidence is random between 0.80 and 0.99.
    Main feature is random around normal average and spread from section 11, clamped to 0-1.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc).replace(microsecond=0)

    events = []
    # Generate tick by tick so timestamps go forward chronologically
    for step in range(count_per_group):
        step_offset = (count_per_group - 1 - step) * 5
        timestamp_dt = end_time - timedelta(seconds=step_offset)
        timestamp_str = timestamp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        for zone in ZONES:
            for source in SOURCES:
                cfg = SOURCE_CONFIG[source]
                raw_feature = random.gauss(cfg["normal_avg"], cfg["spread"])
                feature_val = round(_clamp(raw_feature, 0.0, 1.0), 2)
                confidence = round(random.uniform(0.80, 0.99), 2)

                event = {
                    "event_id": _generate_event_id(),
                    "source": source,
                    "zone": zone,
                    "timestamp": timestamp_str,
                    "event_type": cfg["event_type"],
                    "features": {
                        cfg["main_feature"]: feature_val
                    },
                    "confidence": confidence,
                }
                events.append(event)

    return events


def make_anomaly(source: str, zone: str, timestamp: str, event_id: str | None = None) -> dict:
    """
    Return ONE event with the main feature around the anomaly value from section 11.
    """
    if source not in SOURCE_CONFIG:
        raise ValueError(f"Unknown source '{source}'. Must be one of {list(SOURCE_CONFIG.keys())}")
    if zone not in ZONES:
        raise ValueError(f"Unknown zone '{zone}'. Must be one of {ZONES}")

    cfg = SOURCE_CONFIG[source]
    raw_feature = random.gauss(cfg["anomaly_val"], 0.02)
    feature_val = round(_clamp(raw_feature, 0.0, 1.0), 2)
    confidence = round(random.uniform(0.80, 0.99), 2)

    if event_id is None:
        event_id = _generate_event_id()

    return {
        "event_id": event_id,
        "source": source,
        "zone": zone,
        "timestamp": timestamp,
        "event_type": cfg["event_type"],
        "features": {
            cfg["main_feature"]: feature_val
        },
        "confidence": confidence,
    }


def make_test_scenario(count_per_group: int = 200, end_time: datetime | None = None) -> list[dict]:
    """
    Return normal data plus planted anomalies:
    - zone_2: sensor and camera both anomalous within 1 minute of each other (multi_source alert)
    - zone_3: only wifi anomalous (single_source alert)
    - zone_1: nothing planted (stays quiet)
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc).replace(microsecond=0)

    # 1. Normal baseline data
    normal_events = make_normal_data(count_per_group=count_per_group, end_time=end_time)

    # 2. Planted anomalies
    # zone_3: wifi anomaly placed 200s prior (>3 min correlation window before current time)
    ts_wifi = (end_time - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    wifi_anomaly = make_anomaly("wifi", "zone_3", ts_wifi)

    # zone_2: sensor and camera anomalies within 1 minute (30s apart, within 3 min window)
    ts_sensor = (end_time - timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_camera = (end_time - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sensor_anomaly = make_anomaly("sensor", "zone_2", ts_sensor)
    camera_anomaly = make_anomaly("camera", "zone_2", ts_camera)

    all_events = normal_events + [wifi_anomaly, sensor_anomaly, camera_anomaly]

    # Sort events chronologically
    all_events.sort(key=lambda e: e["timestamp"])

    # Ensure clean sequential event IDs across the scenario
    for idx, event in enumerate(all_events, start=1):
        event["event_id"] = f"evt_{idx:03d}"

    return all_events


if __name__ == "__main__":
    current_time = datetime.now(timezone.utc).replace(microsecond=0)
    scenario_events = make_test_scenario(count_per_group=200, end_time=current_time)

    # Identify planted anomalies from the scenario
    planted_details = [
        {
            "source": "wifi",
            "zone": "zone_3",
            "time": (current_time - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "single_source alert expected",
        },
        {
            "source": "sensor",
            "zone": "zone_2",
            "time": (current_time - timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "multi_source alert expected (partner: camera)",
        },
        {
            "source": "camera",
            "zone": "zone_2",
            "time": (current_time - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "multi_source alert expected (partner: sensor, 30s apart)",
        },
    ]

    output_dir = Path(__file__).resolve().parent
    output_path = output_dir / "sample_events.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scenario_events, f, indent=2)

    print(f"Total events created: {len(scenario_events)}")
    print(f"Saved to: {output_path}")
    print("\nPlanted anomalies:")
    for a in planted_details:
        print(f"  - Source: {a['source']}, Zone: {a['zone']}, Time: {a['time']} ({a['note']})")
    print("  - zone_1: Nothing planted (quiet)")
