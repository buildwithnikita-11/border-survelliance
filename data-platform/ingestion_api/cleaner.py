"""
cleaner.py - Data validation and cleaning logic for incoming events.

Strictly enforces rules from shared/schema.md (sections 3, 4, 5, 6, 9).
"""

from datetime import datetime
from typing import Any

VALID_SOURCES = {"camera", "wifi", "sensor", "satellite"}
VALID_ZONES = {"zone_1", "zone_2", "zone_3"}
VALID_EVENT_TYPES = {"movement", "vibration", "signal_change", "surface_change"}

SOURCE_MAPPINGS: dict[str, dict[str, str]] = {
    "camera": {"event_type": "movement", "main_feature": "movement_level"},
    "sensor": {"event_type": "vibration", "main_feature": "vibration_level"},
    "wifi": {"event_type": "signal_change", "main_feature": "signal_change"},
    "satellite": {"event_type": "surface_change", "main_feature": "surface_change"},
}


def validate_and_clean_event(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate incoming event payload according to schema.md contract.
    Raises ValueError with explanatory message on invalid data.
    """
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object")

    # Disallow client-provided event_id per schema.md section 6
    if "event_id" in data:
        raise ValueError("event_id must not be provided in event submission")

    # Validate source
    source = data.get("source")
    if not isinstance(source, str) or source not in VALID_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of: {sorted(VALID_SOURCES)}")

    # Validate zone
    zone = data.get("zone")
    if not isinstance(zone, str) or zone not in VALID_ZONES:
        raise ValueError(f"Invalid zone '{zone}'. Must be one of: {sorted(VALID_ZONES)}")

    # Validate event_type
    event_type = data.get("event_type")
    if not isinstance(event_type, str) or event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event_type '{event_type}'. Must be one of: {sorted(VALID_EVENT_TYPES)}")

    expected_type = SOURCE_MAPPINGS[source]["event_type"]
    if event_type != expected_type:
        raise ValueError(f"event_type '{event_type}' does not match expected '{expected_type}' for source '{source}'")

    # Validate timestamp: UTC ISO 8601 ending in Z
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError("timestamp must be a UTC ISO 8601 string ending with 'Z'")

    try:
        # Validate format parseable as ISO datetime
        clean_ts = timestamp[:-1] + "+00:00"
        datetime.fromisoformat(clean_ts)
    except Exception as e:
        raise ValueError(f"timestamp '{timestamp}' is not a valid ISO 8601 date: {e}")

    # Validate confidence
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number between 0 and 1")
    confidence_float = float(confidence)
    if confidence_float < 0.0 or confidence_float > 1.0:
        raise ValueError("confidence must be between 0 and 1")

    # Validate features
    features = data.get("features")
    if not isinstance(features, dict):
        raise ValueError("features must be a dictionary")

    expected_main_feature = SOURCE_MAPPINGS[source]["main_feature"]
    if expected_main_feature not in features:
        raise ValueError(f"Missing main feature '{expected_main_feature}' for source '{source}'")

    cleaned_features: dict[str, float] = {}
    for feat_name, feat_val in features.items():
        if not isinstance(feat_name, str):
            raise ValueError(f"Feature name must be string: {feat_name}")
        if isinstance(feat_val, bool) or not isinstance(feat_val, (int, float)):
            raise ValueError(f"Feature value for '{feat_name}' must be a number between 0 and 1")
        fval = float(feat_val)
        if fval < 0.0 or fval > 1.0:
            raise ValueError(f"Feature value for '{feat_name}' ({fval}) must be between 0 and 1")
        cleaned_features[feat_name] = fval

    return {
        "source": source,
        "zone": zone,
        "timestamp": timestamp,
        "event_type": event_type,
        "features": cleaned_features,
        "confidence": round(confidence_float, 4),
    }
