"""
camera_simulator.py - Camera input simulator.

Source: camera
Event type: movement
Main feature: movement_level (normal avg 0.15, spread 0.05, anomaly 0.85)
Confidence: 0.80 to 0.99
"""

from pathlib import Path
import sys

# Ensure local simulators package is importable
sim_dir = Path(__file__).resolve().parent
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from common import generate_event, run_simulator_cli


def produce_camera_event(zone: str, is_anomaly: bool = False) -> dict:
    """Generate camera event."""
    return generate_event("camera", zone, is_anomaly=is_anomaly)


if __name__ == "__main__":
    run_simulator_cli("camera", "Camera Movement Simulator")
