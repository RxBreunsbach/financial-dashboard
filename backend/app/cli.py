"""CLI entry points. Currently: backfill historical data into the archive."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.archive.writer import ArchiveWriter
from app.config import ARCHIVE_ROOT, load_sources_config
from app.sources import REGISTRY

IGNORED_CONFIG_KEYS = {"plugin", "series_id", "schedule"}


def backfill(start: datetime, end: datetime, series_ids: set[str] | None = None) -> None:
    writer = ArchiveWriter(ARCHIVE_ROOT)
    entries = load_sources_config()

    if series_ids is not None:
        configured = {entry["series_id"] for entry in entries}
        unknown = series_ids - configured
        if unknown:
            raise SystemExit(f"Unknown series id(s): {', '.join(sorted(unknown))}")
        entries = [entry for entry in entries if entry["series_id"] in series_ids]

    for entry in entries:
        series_id = entry["series_id"]
        plugin_cls = REGISTRY[entry["plugin"]]
        params = {k: v for k, v in entry.items() if k not in IGNORED_CONFIG_KEYS}
        source = plugin_cls(series_id, **params)

        print(f"Backfilling {series_id} ({start.date()} to {end.date()})...")
        df = source.fetch_history(start, end)
        writer.write(df)
        print(f"  wrote {len(df)} rows")


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical data into the archive.")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), defaults to today")
    parser.add_argument(
        "--series",
        default=None,
        help="Comma-separated series id(s) to backfill, e.g. 'stock:URA' or 'fred:DGS10,stock:URA'. "
        "Defaults to every series in config/sources.yaml.",
    )
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end) if args.end else datetime.now(timezone.utc)
    series_ids = {s.strip() for s in args.series.split(",")} if args.series else None
    backfill(start, end, series_ids)


if __name__ == "__main__":
    main()
