# Shared Data Contract

## Event Schema

Every data source must produce an event using these fields:

- `event_id` — unique ID for the event
- `source` — camera, drone, wifi, sensor, or satellite
- `zone` — Zone 1, Zone 2, or Zone 3
- `timestamp` — time when the event occurred
- `event_type` — type of observed activity
- `features` — numeric/raw information used by the AI engine
- `confidence` — confidence of the source observation (0 to 1)

## Example Event

```json
{
  "event_id": "evt_001",
  "source": "wifi",
  "zone": "zone_2",
  "timestamp": "2026-09-28T19:30:00",
  "event_type": "movement",
  "features": {
    "signal_change": 0.72,
    "movement_level": 0.81
  },
  "confidence": 0.88
}