"""Fresh Start: stop any backend/frontend/kiosk processes left over from a
previous run, then relaunch everything cleanly.

Cross-platform (Windows/macOS/Linux): process discovery and termination uses
psutil instead of OS-specific commands (tasklist/ps), and relaunching reuses
the same subprocess-based approach as dev.py and kiosk.py.
"""

from __future__ import annotations

import subprocess
import sys
import time

import psutil
import requests

from app.config import DASHBOARDS_ROOT
from app.dev import BACKEND_URL, FRONTEND_DIR, launch_backend_and_frontend
from app.kiosk import FRONTEND_URL, KIOSK_PROFILE_MARKER, launch_dashboards

HEALTH_POLL_SECONDS = 0.5
HEALTH_TIMEOUT_SECONDS = 30


def _cmdline_text(proc: psutil.Process) -> str:
    try:
        return " ".join(proc.cmdline()).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _cwd(proc: psutil.Process) -> str:
    try:
        return proc.cwd().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return ""


def _is_project_process(proc: psutil.Process) -> bool:
    """Identifies our own backend (uvicorn), frontend (vite), or kiosk browser
    windows among all running processes, by their command line. The "vite" check
    also requires the frontend dir (in cwd or cmdline) so other Vite projects on
    the same machine aren't mistaken for this one."""
    cmdline = _cmdline_text(proc)
    if not cmdline:
        return False
    frontend_dir = str(FRONTEND_DIR).lower()
    if "uvicorn" in cmdline and "app.main:app" in cmdline:
        return True
    if "vite" in cmdline and (frontend_dir in cmdline or _cwd(proc) == frontend_dir):
        return True
    if KIOSK_PROFILE_MARKER in cmdline:
        return True
    return False


def stop_existing() -> None:
    """Terminates any backend, frontend dev server, or kiosk browser window left
    over from a previous run, including their child processes (e.g. the
    uvicorn --reload supervisor/worker pair)."""
    targets = [proc for proc in psutil.process_iter() if _is_project_process(proc)]

    to_stop: list[psutil.Process] = []
    for proc in targets:
        to_stop.append(proc)
        try:
            to_stop.extend(proc.children(recursive=True))
        except psutil.NoSuchProcess:
            pass

    if not to_stop:
        print("No existing backend/frontend/kiosk processes found.")
        return

    print(f"Stopping {len(to_stop)} existing process(es)...")
    for proc in to_stop:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass

    _, alive = psutil.wait_procs(to_stop, timeout=5)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass


def _wait_until_healthy(url: str, timeout: float = HEALTH_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(url, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(HEALTH_POLL_SECONDS)
    return False


def main() -> None:
    stop_existing()

    backend, frontend = launch_backend_and_frontend()
    procs = [backend, frontend]

    print("Waiting for backend...")
    if not _wait_until_healthy(f"{BACKEND_URL}/health"):
        print("Backend did not become healthy in time.", file=sys.stderr)
    print("Waiting for frontend...")
    if not _wait_until_healthy(FRONTEND_URL):
        print("Frontend did not become healthy in time.", file=sys.stderr)

    dashboards = sorted(p.stem for p in DASHBOARDS_ROOT.glob("*.json"))
    if dashboards:
        print(f"Opening dashboards: {', '.join(dashboards)}")
        launch_dashboards(dashboards)

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
