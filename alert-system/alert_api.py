import json
from pathlib import Path
import sqlite3
from typing import Generator, Literal
from fastapi import FastAPI, HTTPException, Query, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from models import Alert, AlertUpdate

app = FastAPI(title="Alert API")

# The dashboard runs on port 5173, so CORS must allow that origin specifically
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB path located relative to this file's directory: ../data/situational.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "situational.db"


# Short-lived DB connection with a timeout because Person 2's engine writes to the same file
def get_db() -> Generator[sqlite3.Connection, None, None]:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database file missing: run Person 1's init script",
        )
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Alerts table missing: run Person 1's init script",
            )
        yield conn
    finally:
        conn.close()


def row_to_alert(row: sqlite3.Row) -> Alert:
    # Parse evidence column from JSON text into a list
    evidence_raw = row["evidence"]
    if isinstance(evidence_raw, str):
        evidence_list = json.loads(evidence_raw)
    else:
        evidence_list = evidence_raw

    return Alert(
        alert_id=row["alert_id"],
        type=row["type"],
        zone=row["zone"],
        created_at=row["created_at"],
        time_window_start=row["time_window_start"],
        time_window_end=row["time_window_end"],
        score=row["score"],
        evidence=evidence_list,
        status=row["status"],
        analyst_note=row["analyst_note"],
    )


# GET /alerts - optional ?status= filter, newest first by created_at
@app.get("/alerts", response_model=list[Alert])
def get_alerts(
    status_filter: Literal["pending", "confirmed", "dismissed", "flagged"] | None = Query(default=None, alias="status"),
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    if status_filter:
        cursor.execute(
            "SELECT * FROM alerts WHERE status = ? ORDER BY created_at DESC",
            (status_filter,),
        )
    else:
        cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return [row_to_alert(r) for r in rows]


# GET /alerts/{alert_id} - get single alert by alert_id
@app.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(alert_id: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )
    return row_to_alert(row)


# PATCH /alerts/{alert_id} - update only status and analyst_note
@app.patch("/alerts/{alert_id}", response_model=Alert)
def update_alert(
    alert_id: str,
    update: AlertUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )

    cursor.execute(
        "UPDATE alerts SET status = ?, analyst_note = ? WHERE alert_id = ?",
        (update.status, update.analyst_note, alert_id),
    )
    db.commit()

    cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
    updated_row = cursor.fetchone()
    return row_to_alert(updated_row)
