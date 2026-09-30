"""
sensor_simulator.py - Ground vibration sensor simulator.

Source: sensor
Event type: vibration
Main feature: vibration_level (normal avg 0.20, spread 0.05, anomaly 0.90)
Confidence: 0.80 to 0.99
"""

from pathlib import Path
import sys

sim_dir = Path(__file__).resolve().parent
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from common import generate_event, run_simulator_cli


def produce_sensor_event(zone: str, is_anomaly: bool = False) -> dict:
    """Generate ground sensor event."""
    return generate_event("sensor", zone, is_anomaly=is_anomaly)


if __name__ == "__main__":
    run_simulator_cli("sensor", "Sensor Vibration Simulator")
