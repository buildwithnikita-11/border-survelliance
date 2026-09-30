"""
satellite_input.py - Satellite surface change simulator.

Source: satellite
Event type: surface_change
Main feature: surface_change (normal avg 0.10, spread 0.05, anomaly 0.75)
Confidence: 0.80 to 0.99
"""

from pathlib import Path
import sys

sim_dir = Path(__file__).resolve().parent
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from common import generate_event, run_simulator_cli


def produce_satellite_event(zone: str, is_anomaly: bool = False) -> dict:
    """Generate satellite event."""
    return generate_event("satellite", zone, is_anomaly=is_anomaly)


if __name__ == "__main__":
    run_simulator_cli("satellite", "Satellite Surface Change Simulator")
