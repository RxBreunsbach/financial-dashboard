"""Dev convenience: run the backend (uvicorn --reload) and frontend (vite dev) together.

Cross-platform (Windows/macOS/Linux) since it only uses subprocess + shutil.which,
no shell-specific syntax. Stops both processes on Ctrl+C or if either one exits.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


def main() -> None:
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found on PATH; install Node.js first.", file=sys.stderr)
        raise SystemExit(1)

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--app-dir", str(BACKEND_DIR)],
        cwd=REPO_ROOT,
    )
    frontend = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND_DIR)
    procs = [backend, frontend]

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping backend and frontend...")
    finally:
        for p in procs:
            try:
                if p.poll() is None:
                    p.terminate()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
