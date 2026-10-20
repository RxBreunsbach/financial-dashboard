"""Launch the dashboard in a headerless (kiosk-style) browser window.

Opens a Chrome/Edge "app mode" window (no address bar, tabs, or bookmarks bar)
pointed at a dashboard. Assumes the frontend dev server is already running
(e.g. via `dev` or `npm run dev`). Cross-platform: only uses shutil.which +
subprocess, no shell-specific syntax.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

FRONTEND_URL = "http://localhost:5173"
# Lets other tools (e.g. fresh_start) recognize kiosk-launched browser windows by
# their --user-data-dir, matched against the full process command line.
KIOSK_PROFILE_MARKER = "financial-dashboard-kiosk"

# Browser executable names to try via PATH, in order, per platform.
BROWSER_CANDIDATES = {
    "win32": {"chrome": ["chrome"], "edge": ["msedge"]},
    "darwin": {
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
    },
    "linux": {"chrome": ["google-chrome", "chromium-browser", "chromium"], "edge": ["microsoft-edge"]},
}

# Edge/Chrome are typically installed here but not added to PATH on Windows.
WINDOWS_FALLBACK_PATHS = {
    "chrome": [
        r"{ProgramFiles}\Google\Chrome\Application\chrome.exe",
        r"{ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        r"{LocalAppData}\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [
        r"{ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        r"{ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
    ],
}


def _find_browser(preferred: str) -> str:
    order = [preferred] + [b for b in ("chrome", "edge") if b != preferred]
    for browser in order:
        for candidate in BROWSER_CANDIDATES.get(sys.platform, {}).get(browser, []):
            if "/" in candidate:
                # Absolute macOS .app path: use directly if it exists.
                if Path(candidate).exists():
                    return candidate
            else:
                path = shutil.which(candidate)
                if path:
                    return path

        if sys.platform == "win32":
            env = {
                "ProgramFiles": os.environ.get("ProgramFiles", r"C:\Program Files"),
                "ProgramFiles(x86)": os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                "LocalAppData": os.environ.get("LocalAppData", ""),
            }
            for template in WINDOWS_FALLBACK_PATHS.get(browser, []):
                path = Path(template.format(**env))
                if path.exists():
                    return str(path)

    raise SystemExit(
        "Could not find Chrome or Edge. Install one of them, or open "
        f"{FRONTEND_URL} manually in app mode."
    )


def launch_dashboards(
    dashboards: list[str],
    browser: str = "chrome",
    width: int = 960,
    height: int = 800,
) -> None:
    """Opens one headerless browser window per dashboard name."""
    browser_path = _find_browser(browser)
    for index, dashboard in enumerate(dashboards):
        url = f"{FRONTEND_URL}/?dashboard={dashboard}"
        subprocess.Popen(
            [
                browser_path,
                f"--app={url}",
                f"--window-size={width},{height}",
                f"--window-position={index * width},0",
                "--new-window",
                f"--user-data-dir={_profile_dir(dashboard)}",
            ]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Open one or more dashboards in headerless browser windows.")
    parser.add_argument(
        "dashboards", nargs="*", default=["rates"], help="Dashboard name(s) (default: rates)"
    )
    parser.add_argument("--browser", choices=["chrome", "edge"], default="chrome")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args()

    launch_dashboards(args.dashboards, args.browser, args.width, args.height)


def _profile_dir(dashboard: str) -> str:
    # Separate per-dashboard Chrome profile dirs so each --app window opens
    # as its own top-level window instead of a tab in an existing instance.
    import tempfile

    return str(Path(tempfile.gettempdir()) / "financial-dashboard-kiosk" / dashboard)


if __name__ == "__main__":
    main()
