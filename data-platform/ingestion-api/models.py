"""
models.py - Re-export from ingestion_api.models
"""
from pathlib import Path
import sys

pkg_dir = Path(__file__).resolve().parent.parent / "ingestion_api"
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from models import EventCreate, EventResponse  # noqa: F401
