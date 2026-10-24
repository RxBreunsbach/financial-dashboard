"""Background scheduler: runs each configured source on its cron schedule, appending fresh data to the archive."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.archive.writer import ArchiveWriter
from app.config import ARCHIVE_ROOT, load_sources_config
from app.sources import REGISTRY

logger = logging.getLogger(__name__)

IGNORED_CONFIG_KEYS = {"plugin", "series_id", "schedule"}
LOOKBACK_DAYS = 7  # re-fetch a rolling window so revisions/missed runs are caught, not just "today"


def _todays_bar_is_complete(entry: dict) -> bool:
    """For stock series re-fetched every 15 minutes after market close: once today's
    bar already has a non-null close in the archive (Yahoo finalized it, or Finnhub's
    patch filled it), further retries this evening are pointless - skip them."""
    if entry.get("plugin") != "stock":
        return False
    source, _, series = entry["series_id"].partition(":")
    today = datetime.now().date()  # local date, matching the cron schedule's local tz
    path = ARCHIVE_ROOT / source / series / f"{today:%Y-%m}.parquet"
    if not path.exists():
        return False
    df = pd.read_parquet(path)
    todays_rows = df[pd.to_datetime(df["timestamp"]).dt.date == today]
    return not todays_rows.empty and bool(pd.notna(todays_rows["value"]).all())


def _run_job(entry: dict) -> None:
    series_id = entry["series_id"]
    if _todays_bar_is_complete(entry):
        logger.info("Skipping refresh for %s; today's bar is already complete", series_id)
        return
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
    """Builds (but does not start) a scheduler with one cron job per configured series that has a schedule.

    Also schedules a one-off catch-up run for each, firing shortly after the scheduler starts.
    The cron trigger alone only fires at its scheduled time (e.g. 6am) *while the process happens
    to be running*; any ticks missed because the backend was stopped (laptop asleep, dev server not
    running, etc.) would otherwise leave the archive stale until the next tick. The catch-up run uses
    the same rolling LOOKBACK_DAYS window, so it's a safe no-op if nothing was actually missed.
    """
    scheduler = BackgroundScheduler()
    for entry in load_sources_config():
        schedule = entry.get("schedule")
        if not schedule:
            continue
        series_id = entry["series_id"]
        scheduler.add_job(
            _run_job,
            trigger=CronTrigger.from_crontab(schedule),
            args=[entry],
            id=series_id,
            replace_existing=True,
            # Same APScheduler pitfall as the catch-up job below: the default
            # misfire_grace_time is 1 second, so any tick where the background
            # scheduler thread wakes up even slightly late (routine under real
            # process load) is silently dropped as "missed" instead of run late,
            # which otherwise leaves recurring refreshes never actually firing.
            misfire_grace_time=None,
        )
        scheduler.add_job(
            _run_job,
            trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
            args=[entry],
            id=f"{series_id}:startup-catchup",
            replace_existing=True,
            # Default misfire_grace_time is 1 second; the scheduler's first poll after
            # start() routinely lands a bit later than that, which would otherwise cause
            # every catch-up job to be silently skipped as "missed" instead of running.
            misfire_grace_time=None,
        )
    return scheduler
