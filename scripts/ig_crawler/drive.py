"""Driver: keep re-running the creators phase until DONE or a hard total
time limit. Every run is checkpointed, so a kill is safe.
"""
from __future__ import annotations

import subprocess
import sys
import time

PHASE = sys.argv[1] if len(sys.argv) > 1 else "run_creators.py"
LIMIT_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 120
HERE = __file__.rsplit("\\", 1)[0]

end = time.time() + LIMIT_MIN * 60
n = 0
while time.time() < end:
    n += 1
    r = subprocess.run(
        [sys.executable, f"{HERE}\\{PHASE}"],
        cwd=HERE, timeout=1100,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (r.stdout or "").strip().splitlines()
    print(f"--- pass {n}: rc={r.returncode} ---", flush=True)
    for line in tail[-4:]:
        print("   " + line, flush=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        for line in err[-5:]:
            print("   ERR " + line, flush=True)
    if any(l.startswith("DONE:") for l in tail[-6:]) or any(
            l.startswith("DONE:") for l in (r.stderr or "").splitlines()):
        print("phase reported DONE; stopping driver", flush=True)
        break
else:
    print(f"driver time limit ({LIMIT_MIN} min) reached after {n} passes", flush=True)
