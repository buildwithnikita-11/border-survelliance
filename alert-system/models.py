from typing import Literal
from pydantic import BaseModel, Field, ValidationError


# Model representing a single piece of anomaly evidence supporting an alert
class Evidence(BaseModel):
    event_id: str
    source: Literal["camera", "wifi", "sensor", "satellite"]
    main_feature: str
    value: float
    normal_average: float
    deviation: float
    confidence: float
    reason: str


# Model representing an alert
class Alert(BaseModel):
    alert_id: str
    type: Literal["multi_source", "single_source"]
    zone: Literal["zone_1", "zone_2", "zone_3"]
    created_at: str
    time_window_start: str
    time_window_end: str
    score: float = Field(ge=0.0, le=10.0)
    evidence: list[Evidence]
    status: Literal["pending", "confirmed", "dismissed", "flagged"]
    analyst_note: str


# Model for updating alert status and note via PATCH /alerts/{alert_id}
class AlertUpdate(BaseModel):
    status: Literal["pending", "confirmed", "dismissed", "flagged"]
    analyst_note: str


if __name__ == "__main__":
    # Sample alert data from shared/schema.md section 7
    sample_alert = {
        "alert_id": "alert_001",
        "type": "multi_source",
        "zone": "zone_2",
        "created_at": "2026-09-28T19:30:30Z",
        "time_window_start": "2026-09-28T19:28:00Z",
        "time_window_end": "2026-09-28T19:31:00Z",
        "score": 8.2,
        "evidence": [
            {
                "event_id": "evt_001",
                "source": "wifi",
                "main_feature": "signal_change",
                "value": 0.72,
                "normal_average": 0.15,
                "deviation": 5.1,
                "confidence": 0.88,
                "reason": "wifi signal_change is far above normal for zone_2",
            }
        ],
        "status": "pending",
        "analyst_note": "",
    }

    # Test 1: build an Alert from the section 7 example, copied exactly.
    print("--- Test 1: Valid section 7 example ---")
    try:
        alert = Alert(**sample_alert)
        print("Validated alert:", alert)
        print("Test 1: PASS")
    except Exception as e:
        print("Error:", e)
        print("Test 1: FAIL")

    # Test 2: invalid status -> rejected. Print the real error.
    print("\n--- Test 2: Invalid status ---")
    try:
        test2_data = sample_alert.copy()
        test2_data["status"] = "in_review"
        Alert(**test2_data)
        print("Test 2: FAIL")
    except ValidationError as e:
        print("Real error:\n", e)
        print("Test 2: PASS")
    except Exception as e:
        print("Unexpected error:", e)
        print("Test 2: FAIL")

    # Test 3: unknown zone ("zone_9") -> rejected.
    print("\n--- Test 3: Unknown zone ('zone_9') ---")
    try:
        test3_data = sample_alert.copy()
        test3_data["zone"] = "zone_9"
        Alert(**test3_data)
        print("Test 3: FAIL")
    except ValidationError as e:
        print("Real error:\n", e)
        print("Test 3: PASS")
    except Exception as e:
        print("Unexpected error:", e)
        print("Test 3: FAIL")

    # Test 4: missing required field -> rejected.
    print("\n--- Test 4: Missing required field ---")
    try:
        test4_data = sample_alert.copy()
        del test4_data["alert_id"]
        Alert(**test4_data)
        print("Test 4: FAIL")
    except ValidationError as e:
        print("Real error:\n", e)
        print("Test 4: PASS")
    except Exception as e:
        print("Unexpected error:", e)
        print("Test 4: FAIL")

    # Test 5: score of 11 -> rejected.
    print("\n--- Test 5: Score of 11 ---")
    try:
        test5_data = sample_alert.copy()
        test5_data["score"] = 11
        Alert(**test5_data)
        print("Test 5: FAIL")
    except ValidationError as e:
        print("Real error:\n", e)
        print("Test 5: PASS")
    except Exception as e:
        print("Unexpected error:", e)
        print("Test 5: FAIL")
