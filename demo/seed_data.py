"""
Seed script for Person 3 demo.
Generates and POSTs at least 40 normal baseline events per source and zone
(4 sources x 3 zones = 12 groups, 480 total events) to the Ingestion API
at http://localhost:8000/events.

Conforms strictly to shared/schema.md sections 3, 4, 5, 6, 11.
"""

import datetime
import json
import random
import sys
import urllib.error
import urllib.request

# Configuration
API_URL = "http://localhost:8000/events"
EVENTS_PER_GROUP = 40  # 40 events per group (>= 30 required by engine baseline)

# Fixed lists from schema.md section 3 & 5
SOURCES = {
    "camera": {"event_type": "movement", "feature": "movement_level", "avg": 0.15, "spread": 0.05},
    "sensor": {"event_type": "vibration", "feature": "vibration_level", "avg": 0.20, "spread": 0.05},
    "wifi": {"event_type": "signal_change", "feature": "signal_change", "avg": 0.15, "spread": 0.05},
    "satellite": {"event_type": "surface_change", "feature": "surface_change", "avg": 0.10, "spread": 0.05},
}
ZONES = ["zone_1", "zone_2", "zone_3"]


def generate_normal_event(source: str, zone: str, timestamp_utc: str) -> dict:
    """Generate a single normal event adhering to schema.md sections 5, 6, 11."""
    config = SOURCES[source]
    
    # Normal feature value clamped between 0 and 1
    raw_val = random.gauss(config["avg"], config["spread"])
    feature_val = round(max(0.0, min(1.0, raw_val)), 4)
    
    # Confidence: normal events 0.80 to 0.99 (schema.md section 11)
    confidence = round(random.uniform(0.80, 0.99), 2)
    
    # Schema section 6 payload (no event_id, created by DB)
    return {
        "source": source,
        "zone": zone,
        "timestamp": timestamp_utc,
        "event_type": config["event_type"],
        "features": {
            config["feature"]: feature_val
        },
        "confidence": confidence,
    }


def post_event(event: dict) -> dict:
    """POST event to Ingestion API and return JSON response or raise error."""
    payload = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def main():
    print(f"Starting seed_data.py...")
    print(f"Target Ingestion API: {API_URL}")
    print(f"Groups: {len(SOURCES)} sources x {len(ZONES)} zones = {len(SOURCES) * len(ZONES)} groups")
    print(f"Events per group: {EVENTS_PER_GROUP} (Total events: {len(SOURCES) * len(ZONES) * EVENTS_PER_GROUP})\n")

    # Quick connectivity check
    try:
        urllib.request.urlopen("http://localhost:8000/health", timeout=2)
    except urllib.error.URLError as err:
        print(f"[ERROR] Cannot connect to Ingestion API at http://localhost:8000: {err}")
        print("Please ensure the Ingestion API (Person 1) is running before seeding data.")
        sys.exit(1)
    except Exception as err:
        print(f"[ERROR] Connection check failed: {err}")
        sys.exit(1)

    # Base time for past timestamps (UTC with trailing Z, schema.md section 4)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    total_posted = 0
    errors = 0

    for source in SOURCES:
        for zone in ZONES:
            print(f"Seeding {source} + {zone} ({EVENTS_PER_GROUP} events)...")
            for i in range(EVENTS_PER_GROUP):
                # Generate past timestamps spaced 5 seconds apart
                seconds_ago = (EVENTS_PER_GROUP - i) * 5 + 300
                ts = now_utc - datetime.timedelta(seconds=seconds_ago)
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

                event = generate_normal_event(source, zone, ts_str)
                try:
                    resp = post_event(event)
                    total_posted += 1
                except urllib.error.HTTPError as err:
                    errors += 1
                    err_body = err.read().decode("utf-8")
                    print(f"  [HTTP {err.code}] Rejection for {source} in {zone}: {err_body}")
                except urllib.error.URLError as err:
                    errors += 1
                    print(f"  [Connection Error] {err}")
                    print("Stopping further requests due to network error.")
                    sys.exit(1)

    print("\n---------------------------------------------------")
    print(f"Seeding finished: {total_posted} events successfully posted, {errors} errors.")
    print("---------------------------------------------------")


if __name__ == "__main__":
    main()
