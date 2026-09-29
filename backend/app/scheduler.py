"""Background scheduler: runs each configured source on its cron schedule, appending fresh data to the archive."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.archive.writer import ArchiveWriter
from app.config import ARCHIVE_ROOT, load_sources_config
from app.sources import REGISTRY

logger = logging.getLogger(__name__)

IGNORED_CONFIG_KEYS = {"plugin", "series_id", "schedule"}
LOOKBACK_DAYS = 7  # re-fetch a rolling window so revisions/missed runs are caught, not just "today"


def _run_job(entry: dict) -> None:
    series_id = entry["series_id"]
    try:
        plugin_cls = REGISTRY[entry["plugin"]]
        params = {k: v for k, v in entry.items() if k not in IGNORED_CONFIG_KEYS}
        source = plugin_cls(series_id, **params)

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=LOOKBACK_DAYS)
        df = source.fetch_history(start, end)

        ArchiveWriter(ARCHIVE_ROOT).write(df)
        logger.info("Scheduled refresh for %s wrote %d rows", series_id, len(df))
    except Exception:
        logger.exception("Scheduled refresh failed for %s", series_id)


def create_scheduler() -> BackgroundScheduler:
    """Builds (but does not start) a scheduler with one cron job per configured series that has a schedule."""
    scheduler = BackgroundScheduler()
    for entry in load_sources_config():
        schedule = entry.get("schedule")
        if not schedule:
            continue
        scheduler.add_job(
            _run_job,
            trigger=CronTrigger.from_crontab(schedule),
            args=[entry],
            id=entry["series_id"],
            replace_existing=True,
        )
    return scheduler
