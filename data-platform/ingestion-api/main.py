"""
main.py - Re-export app from ingestion_api.main
"""
from pathlib import Path
import sys

pkg_dir = Path(__file__).resolve().parent.parent / "ingestion_api"
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
