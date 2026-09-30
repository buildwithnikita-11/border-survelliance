"""
wifi_simulator.py - Wi-Fi signal simulator.

Source: wifi
Event type: signal_change
Main feature: signal_change (normal avg 0.15, spread 0.05, anomaly 0.80)
Confidence: 0.80 to 0.99
"""

from pathlib import Path
import sys

sim_dir = Path(__file__).resolve().parent
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from common import generate_event, run_simulator_cli


def produce_wifi_event(zone: str, is_anomaly: bool = False) -> dict:
    """Generate wifi event."""
    return generate_event("wifi", zone, is_anomaly=is_anomaly)


if __name__ == "__main__":
    run_simulator_cli("wifi", "Wi-Fi Signal Simulator")
