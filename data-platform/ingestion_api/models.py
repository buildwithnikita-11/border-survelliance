"""
models.py - Pydantic models for Ingestion API events.

Strictly adheres to schema.md section 6:
- event_id
- source
- zone
- timestamp
- event_type
- features
- confidence
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, model_validator
from cleaner import validate_and_clean_event


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    zone: str
    timestamp: str
    event_type: str
    features: dict[str, float]
    confidence: float

    @model_validator(mode="before")
    @classmethod
    def validate_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return validate_and_clean_event(data)
        return data


class EventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    source: str
    zone: str
    timestamp: str
    event_type: str
    features: dict[str, float]
    confidence: float
