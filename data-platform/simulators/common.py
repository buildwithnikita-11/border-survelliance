"""
common.py - Shared utilities for sensor simulators.

Adheres strictly to shared/schema.md:
- Sections 3 & 5: Fixed lists and main features.
- Section 6: Event payload format (simulators do not provide event_id).
- Section 11: Normal distributions and planted anomaly values.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import socket
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

ZONES = ["zone_1", "zone_2", "zone_3"]

SIMULATOR_CONFIGS: dict[str, dict[str, Any]] = {
    "camera": {
        "source": "camera",
        "event_type": "movement",
        "main_feature": "movement_level",
        "normal_avg": 0.15,
        "spread": 0.05,
        "anomaly_val": 0.85,
    },
    "sensor": {
        "source": "sensor",
        "event_type": "vibration",
        "main_feature": "vibration_level",
        "normal_avg": 0.20,
        "spread": 0.05,
        "anomaly_val": 0.90,
    },
    "wifi": {
        "source": "wifi",
        "event_type": "signal_change",
        "main_feature": "signal_change",
        "normal_avg": 0.15,
        "spread": 0.05,
        "anomaly_val": 0.80,
    },
    "satellite": {
        "source": "satellite",
        "event_type": "surface_change",
        "main_feature": "surface_change",
        "normal_avg": 0.10,
        "spread": 0.05,
        "anomaly_val": 0.75,
    },
}


def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, val))


def generate_event(source: str, zone: str, is_anomaly: bool = False) -> dict[str, Any]:
    """
    Generate an event without event_id.
    Simulators send everything except event_id (schema.md section 6).
    """
    if source not in SIMULATOR_CONFIGS:
        raise ValueError(f"Unknown source: {source}")
    if zone not in ZONES:
        raise ValueError(f"Invalid zone: {zone}. Must be one of {ZONES}")

    cfg = SIMULATOR_CONFIGS[source]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if is_anomaly:
        feature_val = cfg["anomaly_val"]
        confidence = 0.95
    else:
        raw_val = random.gauss(cfg["normal_avg"], cfg["spread"])
        feature_val = round(clamp(raw_val), 4)
        confidence = round(random.uniform(0.80, 0.99), 2)

    return {
        "source": source,
        "zone": zone,
        "timestamp": timestamp,
        "event_type": cfg["event_type"],
        "features": {cfg["main_feature"]: feature_val},
        "confidence": confidence,
    }


def is_server_listening(api_url: str) -> bool:
    """Quick check if endpoint host and port are listening."""
    try:
        parsed = urllib.parse.urlparse(api_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except Exception:
        return False


def post_event_to_api(event: dict[str, Any], api_url: str = "http://localhost:8000/events") -> tuple[bool, Any]:
    """
    Post event JSON to Ingestion API.
    Returns (success: bool, response_or_error: Any).
    """
    if not is_server_listening(api_url):
        return False, f"Ingestion API not reachable at {api_url}"

    data_bytes = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            resp_body = resp.read().decode("utf-8")
            return True, json.loads(resp_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, str(e)


def run_simulator_cli(source: str, title: str, custom_args: list[str] | None = None) -> list[dict[str, Any]]:
    """Standard CLI handler for all simulators."""
    parser = argparse.ArgumentParser(description=title)
    parser.add_argument("--anomaly", action="store_true", help="Generate an on-demand anomaly")
    parser.add_argument("--zone", type=str, default=None, choices=ZONES, help="Target zone (zone_1, zone_2, zone_3)")
    parser.add_argument("--loop", action="store_true", help="Run continuously sending events approximately every 5 seconds")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000/events", help="Ingestion API URL")
    parser.add_argument("--no-post", action="store_true", help="Print JSON only, do not POST to API")

    args = parser.parse_args(custom_args)

    if args.anomaly:
        target_zone = args.zone if args.zone else "zone_2"
        event = generate_event(source, target_zone, is_anomaly=True)
        print(json.dumps(event, indent=2), flush=True)

        if not args.no_post:
            success, res = post_event_to_api(event, args.api_url)
            if success:
                print(f"[API SUCCESS] Event ingested with event_id: {res.get('event_id')}", flush=True)
            else:
                print(f"[API INFO] {res}", flush=True)
        return [event]

    target_zones = [args.zone] if args.zone else ZONES
    produced_events: list[dict[str, Any]] = []

    try:
        while True:
            for zone in target_zones:
                event = generate_event(source, zone, is_anomaly=False)
                produced_events.append(event)
                print(json.dumps(event, indent=2), flush=True)

                if not args.no_post:
                    success, res = post_event_to_api(event, args.api_url)
                    if success:
                        print(f"[API SUCCESS] Event ingested with event_id: {res.get('event_id')}", flush=True)
                    else:
                        print(f"[API INFO] {res}", flush=True)

            if not args.loop:
                break

            time.sleep(5.0)
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.", flush=True)

    return produced_events
