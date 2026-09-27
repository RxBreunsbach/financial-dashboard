from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.archive.writer import ArchiveWriter


def _df(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["timestamp", "series_id", "value"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def test_write_creates_partition_file(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    df = _df([("2024-01-02", "fred:DGS10", 4.1), ("2024-01-03", "fred:DGS10", 4.2)])

    writer.write(df)

    path = tmp_path / "fred" / "DGS10" / "2024-01.parquet"
    assert path.exists()
    result = pd.read_parquet(path)
    assert len(result) == 2


def test_write_splits_across_months_and_series(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    df = _df(
        [
            ("2024-01-31", "fred:DGS10", 4.1),
            ("2024-02-01", "fred:DGS10", 4.15),
            ("2024-02-01", "fred:DGS2", 4.9),
        ]
    )

    writer.write(df)

    assert (tmp_path / "fred" / "DGS10" / "2024-01.parquet").exists()
    assert (tmp_path / "fred" / "DGS10" / "2024-02.parquet").exists()
    assert (tmp_path / "fred" / "DGS2" / "2024-02.parquet").exists()


def test_write_is_idempotent_on_rewrite(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    df = _df([("2024-01-02", "fred:DGS10", 4.1)])

    writer.write(df)
    writer.write(df)

    result = pd.read_parquet(tmp_path / "fred" / "DGS10" / "2024-01.parquet")
    assert len(result) == 1


def test_write_updates_revised_value_for_same_timestamp(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    writer.write(_df([("2024-01-02", "fred:DGS10", 4.1)]))
    writer.write(_df([("2024-01-02", "fred:DGS10", 4.2)]))

    result = pd.read_parquet(tmp_path / "fred" / "DGS10" / "2024-01.parquet")
    assert len(result) == 1
    assert result["value"].iloc[0] == pytest.approx(4.2)


def test_write_empty_dataframe_is_noop(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    writer.write(pd.DataFrame(columns=["timestamp", "series_id", "value"]))

    assert list(tmp_path.iterdir()) == []


def test_write_missing_required_column_raises(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    df = pd.DataFrame({"timestamp": [pd.Timestamp.now(tz="UTC")], "series_id": ["fred:DGS10"]})

    with pytest.raises(ValueError):
        writer.write(df)


def test_write_leaves_no_temp_files_behind(tmp_path: Path) -> None:
    writer = ArchiveWriter(tmp_path)
    writer.write(_df([("2024-01-02", "fred:DGS10", 4.1)]))
    writer.write(_df([("2024-01-03", "fred:DGS10", 4.2)]))

    partition_dir = tmp_path / "fred" / "DGS10"
    assert [p.name for p in partition_dir.iterdir()] == ["2024-01.parquet"]


def test_concurrent_writes_never_corrupt_partition_file(tmp_path: Path) -> None:
    # Regression test: partition writes must be atomic (temp file + rename) so a
    # reader never sees a torn/corrupt file even under concurrent writers
    # (e.g. the live-stream WebSocket and a manual backfill running at once).
    from concurrent.futures import ThreadPoolExecutor

    writer = ArchiveWriter(tmp_path)
    path = tmp_path / "fred" / "DGS10" / "2024-01.parquet"

    def write_one(i: int) -> None:
        writer.write(_df([(f"2024-01-{(i % 28) + 1:02d}", "fred:DGS10", float(i))]))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_one, range(50)))

    # Must be readable (never a torn/partial file) after concurrent writes.
    result = pd.read_parquet(path)
    assert not result.empty
