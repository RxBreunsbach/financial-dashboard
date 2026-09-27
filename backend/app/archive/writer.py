"""Append-only Parquet archive writer.

Layout: data/archive/<source>/<series>/<YYYY-MM>.parquet
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"timestamp", "series_id", "value"}


class ArchiveWriter:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = Path(archive_root)

    def write(self, df: pd.DataFrame) -> None:
        """Append rows to the archive, partitioned by source/series/month.

        Rows are grouped by their `series_id` prefix (e.g. "fred:DGS10" ->
        source "fred", series "DGS10"). Existing partitions are merged with
        new rows and de-duplicated on `timestamp` (keeping the newest value,
        since upstream sources sometimes revise recent history) rather than
        ever deleting previously archived rows outright.
        """
        if df.empty:
            return
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        for series_id, series_df in df.groupby("series_id"):
            source, _, series = str(series_id).partition(":")
            series_df = series_df.sort_values("timestamp")
            months = series_df["timestamp"].dt.strftime("%Y-%m")
            for month, month_df in series_df.groupby(months):
                self._write_partition(source, series, str(month), month_df)

    def _write_partition(self, source: str, series: str, month: str, month_df: pd.DataFrame) -> None:
        partition_dir = self.archive_root / source / series
        partition_dir.mkdir(parents=True, exist_ok=True)
        path = partition_dir / f"{month}.parquet"

        if path.exists():
            # Reading can also transiently hit PermissionError on Windows if it races
            # with another thread's os.replace() on this same path below.
            existing = self._retry_on_permission_error(lambda: pd.read_parquet(path))
            combined = pd.concat([existing, month_df], ignore_index=True)
            combined = combined.drop_duplicates(subset="timestamp", keep="last")
            combined = combined.sort_values("timestamp").reset_index(drop=True)
        else:
            combined = month_df.reset_index(drop=True)

        # Write to a temp file and rename atomically, so a concurrent reader/writer
        # (e.g. the live-stream WebSocket and a manual backfill) never sees a
        # torn/corrupt partial file, even if both processes write around the same time.
        tmp_path = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.tmp")
        combined.to_parquet(tmp_path, index=False)
        self._retry_on_permission_error(lambda: os.replace(tmp_path, path))

    @staticmethod
    def _retry_on_permission_error(func, attempts: int = 15):
        """Windows can transiently raise PermissionError when a file is briefly
        locked by another thread's read/rename; POSIX never does. Retry it out."""
        for attempt in range(attempts):
            try:
                return func()
            except PermissionError:
                if attempt == attempts - 1:
                    raise
                time.sleep(min(0.02 * (attempt + 1), 0.25))
