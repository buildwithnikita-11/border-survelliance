import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(r"D:\border-survelliance-main")
SIM_DIR = REPO_ROOT / "data-platform" / "simulators"

def run_sim(script, *args):
    cmd = [sys.executable, str(SIM_DIR / script), *args]
    print(f"\n>>> Running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, flush=True)
    if result.returncode != 0:
        print("ERROR:", result.stderr, flush=True)

def countdown(seconds, label):
    print(f"\n--- {label} ({seconds}s) ---", flush=True)
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print()

print("=== DEMO SEQUENCE START ===", flush=True)
print("Make sure ingestion API, all 4 loop simulators, engine_runner.py,", flush=True)
print("alert_api.py, and the dashboard are already running before this starts.", flush=True)

countdown(5, "Starting in")

print("\n### Scenario 1: Normal baseline (nothing happens) ###", flush=True)
countdown(5, "Showing normal dashboard state")

print("\n### Scenario 2: Multi-source anomaly in zone_1 ###", flush=True)
run_sim("sensor_simulator.py", "--anomaly", "--zone", "zone_1")
time.sleep(2)
run_sim("camera_simulator.py", "--anomaly", "--zone", "zone_1")

countdown(25, "Waiting for engine to detect and correlate")
print(">>> Refresh the dashboard NOW - a new multi_source alert should appear", flush=True)

countdown(8, "Pausing on the alert detail / evidence view")

print("\n### Scenario 3: Second zone anomaly (zone_3) ###", flush=True)
run_sim("wifi_simulator.py", "--anomaly", "--zone", "zone_3")
time.sleep(2)
run_sim("satellite_input.py", "--anomaly", "--zone", "zone_3")

countdown(25, "Waiting for engine to detect and correlate")
print(">>> Refresh the dashboard NOW - zone_3 alert should appear", flush=True)

countdown(8, "Pausing to show Confirm/Dismiss/Flag controls")

print("\n=== DEMO SEQUENCE END ===", flush=True)