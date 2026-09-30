"""
camera_input.py - Alias for camera_simulator.py
"""

from pathlib import Path
import sys

sim_dir = Path(__file__).resolve().parent
if str(sim_dir) not in sys.path:
    sys.path.insert(0, str(sim_dir))

from camera_simulator import produce_camera_event, run_simulator_cli

if __name__ == "__main__":
    run_simulator_cli("camera", "Camera Movement Simulator")
