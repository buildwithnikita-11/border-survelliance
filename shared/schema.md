# Shared Data Contract

STATUS: DRAFT until all 3 members reply "agreed". After that it is LOCKED.
Rule: nobody changes this file alone. Any change must be approved by all 3
members and announced in the team chat.

## 1. Owners
- Person 1: data-platform/  (simulators, ingestion API, database setup)
- Person 2: ai-engine/      (baseline, anomaly detection, correlation, scoring)
- Person 3: alert-system/ + dashboard/ + demo/
- Nobody edits another person's folder. Ask the owner instead.

## 2. Tech versions
- Python 3.11, FastAPI, SQLite
- Node 18 or higher, React

## 3. Fixed lists (exact spelling, lowercase)
- source: "camera", "wifi", "sensor", "satellite"
- zone: "zone_1", "zone_2", "zone_3"
- event_type: "movement", "vibration", "signal_change", "surface_change"
- alert status: "pending", "confirmed", "dismissed", "flagged"
- alert type: "multi_source", "single_source"

## 4. Time rules
- All timestamps are UTC, ISO 8601, with a Z at the end.
- Example: 2026-09-28T19:30:00Z

## 5. Main feature per source
Every event must contain its source's main feature inside "features".
The engine checks ONLY the main feature. Other features are allowed
but are only shown as extra information.
All feature values are numbers from 0 to 1.

| source    | event_type      | main feature     |
|-----------|-----------------|------------------|
| camera    | movement        | movement_level   |
| sensor    | vibration       | vibration_level  |
| wifi      | signal_change   | signal_change    |
| satellite | surface_change  | surface_change   |

## 6. Event (Person 1 writes, Person 2 reads)
{
  "event_id": "evt_001",
  "source": "wifi",
  "zone": "zone_2",
  "timestamp": "2026-09-28T19:30:00Z",
  "event_type": "signal_change",
  "features": {
    "signal_change": 0.72
  },
  "confidence": 0.88
}
- event_id is created by the database. Simulators send everything except event_id.
- confidence is 0 to 1. The engine ignores events with confidence below 0.5.

## 7. Alert (Person 2 writes, Person 3 reads)
{
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
      "reason": "wifi signal_change is far above normal for zone_2"
    }
  ],
  "status": "pending",
  "analyst_note": ""
}
- deviation = how many standard deviations away from normal (always positive).
- score goes from 0 to 10. Higher = review first.
- reason is plain English, written by Person 2's code. Person 3 shows it as is.

## 8. Database (one SQLite file: data/situational.db)
- Person 1 owns database.py and creates BOTH tables. Nobody else creates tables.
- The data/ folder is in .gitignore. Each person creates their own local
  file using Person 1's init script and the seed script.

Table events:
  event_id (text, primary key), source, zone, timestamp, event_type,
  features (text, JSON), confidence (real)

Table alerts:
  alert_id (text, primary key), type, zone, created_at, time_window_start,
  time_window_end, score (real), evidence (text, JSON list), status,
  analyst_note

## 9. APIs
Ingestion API (Person 1) runs on port 8000
- POST  /events    body = event without event_id, returns the full event
- GET   /events    optional filters: zone, source, since (timestamp)
- Bad data (wrong source, zone or event_type, missing main feature,
  value outside 0-1) returns HTTP 422 and is NOT stored.

Alert API (Person 3) runs on port 8001
- GET   /alerts          optional filter: status. Newest first.
- GET   /alerts/{alert_id}
- PATCH /alerts/{alert_id}   body = { "status": "...", "analyst_note": "..." }
- Turn on CORS for http://localhost:5173 so the dashboard can call it.

Person 2's engine has no API. It reads the events table and writes rows
into the alerts table. Person 3 never calls the engine directly.

## 10. Engine rules (Person 2 owns these; others need to know them)
- Simulators send 1 event per source per zone every 5 seconds.
- Baseline = average and standard deviation of the main feature over the
  last 200 events for the same source + same zone.
- The engine needs at least 30 events before judging a source + zone.
  Before that, no anomalies are raised.
- Anomaly = deviation of 3 or more.
- Correlation window = 3 minutes. Anomalies in the same zone, from
  2 or more different sources, inside the window = one multi_source alert.
- A single anomaly with no partner after the window closes = single_source
  alert with a lower score.
- No duplicates: if a pending alert already exists for the same zone and
  an overlapping window, the engine updates it instead of creating a new one.
- Score = min(10, 2 x number_of_sources + min(average_deviation, 6))
  For single_source alerts, score is capped at 4.
- The engine runs every 5 seconds.

## 11. Simulator normal values and planted anomalies (Person 1 follows this)
Values are the main feature. Clamp all values to the range 0 to 1.
- camera:    normal average 0.15, spread 0.05    anomaly around 0.85
- sensor:    normal average 0.20, spread 0.05    anomaly around 0.90
- wifi:      normal average 0.15, spread 0.05    anomaly around 0.80
- satellite: normal average 0.10, spread 0.05    anomaly around 0.75
- confidence: normal events 0.80 to 0.99, random.
- Each simulator has a command to trigger an anomaly on demand, for example:
  python sensor_simulator.py --anomaly --zone zone_2
  This is needed so the demo does not depend on luck.

## 12. Checkpoints
- Hour 0-1: this file agreed. Nobody codes before that.
- Hour 1-2: Person 1 gives 2 sample JSON files (10 events).
            Person 2 gives 1 sample alert JSON to Person 3.
- Hour 2 onwards: everyone builds in their own folder using sample data.
- Final stretch: join everything, test the demo end to end.
- Set the real times here: ______________________