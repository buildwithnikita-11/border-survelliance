"""
main.py - FastAPI ingestion application for Person 1 Data Platform.

Runs on port 8000.
Endpoints:
- POST /events : Ingest and validate event without event_id, generate event_id, store, return full event
- GET  /events : Retrieve stored events with optional filters (zone, source, since)
- GET  /       : Service status
- GET  /health : Service health check
"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys
import uuid
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# Ensure data-platform/db and local directory are importable
current_dir = Path(__file__).resolve().parent
db_dir = current_dir.parent / "db"
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(db_dir) not in sys.path:
    sys.path.insert(0, str(db_dir))

from database import get_events, init_db, save_event  # type: ignore
from models import EventCreate, EventResponse  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database and tables exist at startup
    init_db()
    yield


app = FastAPI(title="Situational Awareness Data Platform Ingestion API", lifespan=lifespan)

# Allow CORS for development dashboard and local components
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "Data platform is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_200_OK)
def ingest_event(event_in: EventCreate):
    """
    Ingest a new sensor event without event_id.
    Validates according to shared/schema.md contract, generates event_id,
    stores in database, and returns the full event.
    """
    # Generate unique event_id
    generated_id = f"evt_{uuid.uuid4().hex[:12]}"

    event_record = {
        "event_id": generated_id,
        "source": event_in.source,
        "zone": event_in.zone,
        "timestamp": event_in.timestamp,
        "event_type": event_in.event_type,
        "features": event_in.features,
        "confidence": event_in.confidence,
    }

    try:
        saved_record = save_event(event_record)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist event: {e}",
        )

    return saved_record


@app.get("/events", response_model=list[EventResponse])
def list_events(
    zone: str | None = Query(default=None, description="Filter by zone (e.g. zone_1, zone_2, zone_3)"),
    source: str | None = Query(default=None, description="Filter by source (e.g. camera, sensor, wifi, satellite)"),
    since: str | None = Query(default=None, description="Filter events with timestamp >= since"),
):
    """
    Query stored events with optional filtering by zone, source, or timestamp.
    """
    try:
        events = get_events(zone=zone, source=source, since=since)
        return events
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query events: {e}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
