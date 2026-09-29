# Prototype Demo Script: Border Surveillance System

This document outlines the exact, end-to-end demo sequence for the 3-person border surveillance prototype according to `shared/schema.md`.

---

## Architecture Overview & Ownership
- **Person 1 (`data-platform/`)**: Database initialization, Ingestion API (port 8000), Event simulators.
- **Person 2 (`ai-engine/`)**: Baseline calculation, Anomaly detection, Correlation window (3 min), Scoring.
- **Person 3 (`alert-system/`, `dashboard/`, `demo/`)**: Alert API (port 8001), React Dashboard (port 5173), Demo sequence & Seeding.

---

## Numbered Demo Steps

### Step 1: Initialize Database
- **Owner**: Person 1
- **Status**: **NOT READY** (Person 1's `data-platform/db/database.py` is currently a placeholder)
- **Working Directory**: `c:/Users/thisi/border-survelliance`
- **Command**:
  ```bash
  python data-platform/db/database.py
  ```
- **Expected System State**:
  Creates SQLite database file `data/situational.db` with both tables: `events` and `alerts` (per schema.md section 8).
- **Dashboard State**:
  Dashboard is not running yet.

---

### Step 2: Start Ingestion API
- **Owner**: Person 1
- **Status**: **NOT READY** (Person 1's `data-platform/ingestion-api/main.py` only implements `/` and `/health`; `/events` endpoint is pending)
- **Working Directory**: `c:/Users/thisi/border-survelliance/data-platform/ingestion-api`
- **Command**:
  ```bash
  python -m uvicorn main:app --host 127.0.0.1 --port 8000
  ```
- **Expected System State**:
  Ingestion API listens on `http://localhost:8000`. Exposes `POST /events` and `GET /events` (per schema.md section 9).
- **Dashboard State**:
  Dashboard is not running yet.

---

### Step 3: Seed Baseline Normal Data
- **Owner**: Person 3
- **Status**: **READY**
- **Working Directory**: `c:/Users/thisi/border-survelliance`
- **Command**:
  ```bash
  python demo/seed_data.py
  ```
- **Expected System State**:
  POSTs 40 normal events for each of the 12 source + zone combinations (4 sources x 3 zones = 480 events total) to `http://localhost:8000/events`. All events contain past UTC timestamps ending in `Z`, normal averages/spreads, and random confidences (0.80–0.99) per schema.md section 11.
  This satisfies the AI Engine requirement of at least 30 events before anomaly detection can begin (schema.md section 10).
- **Dashboard State**:
  Dashboard is not running yet.

---

### Step 4: Start AI Engine
- **Owner**: Person 2
- **Status**: **NOT READY** (Person 2's `ai-engine/engine_runner.py` is currently empty)
- **Working Directory**: `c:/Users/thisi/border-survelliance/ai-engine`
- **Command**:
  ```bash
  python engine_runner.py
  ```
- **Expected System State**:
  Reads `events` table every 5 seconds, computes baseline mean and standard deviation over recent events. Since all seeded events are normal, no anomalies or alerts are generated.
- **Dashboard State**:
  Dashboard is not running yet.

---

### Step 5: Start Alert API
- **Owner**: Person 3
- **Status**: **READY**
- **Working Directory**: `c:/Users/thisi/border-survelliance/alert-system`
- **Command**:
  ```bash
  python -m uvicorn alert_api:app --host 127.0.0.1 --port 8001
  ```
- **Expected System State**:
  Alert API listens on `http://localhost:8001` with CORS enabled for `http://localhost:5173`. Exposes `GET /alerts`, `GET /alerts/{alert_id}`, and `PATCH /alerts/{alert_id}`.
- **Dashboard State**:
  Dashboard is not running yet.

---

### Step 6: Start Dashboard
- **Owner**: Person 3
- **Status**: **READY**
- **Working Directory**: `c:/Users/thisi/border-survelliance/dashboard`
- **Command**:
  ```bash
  npm run dev
  ```
- **Expected System State**:
  Vite dev server starts on `http://localhost:5173`. Open `http://localhost:5173` in a web browser.
- **Dashboard State**:
  - **ZoneMap**: Displays 3 cells (`zone_1`, `zone_2`, `zone_3`). All cells are neutral gray (`#f1f5f9`) displaying `"Normal"`, because no pending alerts exist.
  - **AlertList**: Displays `"No alerts found."` (or only non-pending resolved alerts if any exist).
  - **AlertDetail**: Displays empty / waiting state (`"Select an alert to view details"`).
  - **ReviewControls**: Inputs and buttons (Confirm, Dismiss, Flag) are disabled (`disabled=""`) with note placeholder `"Select an alert to review"`.

---

### Step 7: Trigger Multi-Source Anomaly in `zone_2` within 3 Minutes
- **Owner**: Person 1 (simulators) & Person 2 (engine correlation)
- **Status**: **NOT READY** (Person 1's simulator scripts in `data-platform/simulators/` are currently empty placeholders)
- **Correlation Window Rule**: Anomalies from 2 different sources in the same zone within 3 minutes trigger a single `multi_source` alert (schema.md section 10).

#### Step 7a: Trigger 1st Anomaly (Sensor Vibration in `zone_2`)
- **Command**:
  ```bash
  python data-platform/simulators/sensor_simulator.py --anomaly --zone zone_2
  ```
- **Dashboard State**:
  - Sensor emits an anomaly (vibration level ~0.90, deviation >= 3.0).
  - The AI Engine detects the anomaly and opens a 3-minute correlation window for `zone_2`.
  - If window has not elapsed and no second source has triggered, no multi-source alert is formed yet (or single_source alert capped at score 4).

#### Step 7b: Trigger 2nd Anomaly (Wi-Fi Signal Change in `zone_2`) within 3 Minutes
- **Command**:
  ```bash
  python data-platform/simulators/wifi_simulator.py --anomaly --zone zone_2
  ```
- **Dashboard State** (updates within 5 seconds on dashboard poll):
  - **ZoneMap**:
    - The `zone_2` cell immediately changes color to an intense red (`rgba(239, 68, 68, alpha)`), indicating an active pending alert with high score (~8.2).
    - The cell displays: `"1 Pending"` and `"Max Score: 8.2"`.
    - Cells `zone_1` and `zone_3` remain neutral gray (`Normal`).
    - The cell for `zone_2` has an active selection border.
  - **AlertList**:
    - A new alert appears at the very top of the table.
    - Zone: `zone_2`, Type: `multi_source`, Score: `8.2` (colored red for high priority), Status: `pending`.
    - Row is highlighted as selected.
  - **AlertDetail**:
    - Displays Alert ID, Type (`multi_source`), Zone (`zone_2`), Score (`8.2`), Status (`pending`), and 3-minute time window.
    - Displays the Evidence section listing both the `sensor` and `wifi` events, their values, deviations, confidences, and plain English explanation (`reason`).
  - **ReviewControls**:
    - Becomes active and enabled!
    - Buttons **Confirm** (green), **Dismiss** (slate gray), and **Flag** (orange) are enabled.
    - Analyst Note textarea is enabled and ready to accept input.

---

### Step 8: Analyst Review & Decision
- **Owner**: Person 3 (Dashboard UI)
- **Status**: **READY**

1. In the **Analyst Note** textarea, type:
   ```text
   Verified multi-source correlation: sensor vibration accompanied by anomalous wifi signal change. Valid intrusion event.
   ```
2. Click the **Confirm** button.
- **Dashboard State**:
  - Buttons briefly show `"Updating..."` while PATCH `/alerts/{alert_id}` is in flight.
  - On API success, `fetchAlerts` refreshes the dashboard:
    - In **AlertList**, the alert's status updates from `pending` to `confirmed`.
    - In **ZoneMap**, because `zone_2` no longer has any pending alerts, the `zone_2` cell transitions from alert red back to neutral gray (`Normal`).
    - In **AlertDetail**, the status badge displays `confirmed`.
    - Database is persistently updated (verified via `curl http://localhost:8001/alerts/{alert_id}`).
