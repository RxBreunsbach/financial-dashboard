"""Shared configuration: paths and environment loading."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"
ARCHIVE_ROOT = REPO_ROOT / "data" / "archive"
DASHBOARDS_ROOT = REPO_ROOT / "dashboards"

load_dotenv(REPO_ROOT / ".env")


def load_sources_config(path: Path = CONFIG_PATH) -> list[dict]:
    """Load the list of configured series from config/sources.yaml."""
    import yaml

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])
