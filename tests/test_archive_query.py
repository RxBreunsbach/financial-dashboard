from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.archive.query import ArchiveQuery, QueryError, resolve_time_range
from app.archive.writer import ArchiveWriter


def _seed(archive_root: Path) -> None:
    writer = ArchiveWriter(archive_root)
    dates = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    dgs10 = pd.DataFrame({"timestamp": dates, "series_id": "fred:DGS10", "value": [4.0 + 0.1 * i for i in range(10)]})
    dgs2 = pd.DataFrame({"timestamp": dates, "series_id": "fred:DGS2", "value": [4.5 + 0.05 * i for i in range(10)]})
    writer.write(dgs10)
    writer.write(dgs2)


@pytest.fixture
def archive_root(tmp_path: Path) -> Path:
    _seed(tmp_path)
    return tmp_path


def test_resolve_time_range_keyword() -> None:
    now = datetime(2024, 6, 15, tzinfo=timezone.utc)
    start, end = resolve_time_range("1W", now=now)
    assert end == now
    assert (end - start).days == 7


def test_resolve_time_range_ytd() -> None:
    now = datetime(2024, 6, 15, tzinfo=timezone.utc)
    start, end = resolve_time_range("YTD", now=now)
    assert start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert end == now


def test_resolve_time_range_explicit_dates() -> None:
    start, end = resolve_time_range("2024-01-01:2024-01-10")
    assert start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2024, 1, 10, tzinfo=timezone.utc)


def test_resolve_time_range_unrecognized_raises() -> None:
    with pytest.raises(QueryError):
        resolve_time_range("bogus")


def test_run_single_series_raw_values(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "none")

    assert len(points) == 10
    assert points[0]["value"] == pytest.approx(4.0)
    assert points[-1]["value"] == pytest.approx(4.9)


def test_run_expression_subtracts_two_series(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10 - fred:DGS2", "2024-01-01:2024-01-10", "none")

    assert len(points) == 10
    assert points[0]["value"] == pytest.approx(4.0 - 4.5)
    assert points[-1]["value"] == pytest.approx(4.9 - 4.95)


def test_run_pct_change_transform(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "pct_change")

    # first row dropped (NaN from pct_change), 9 remain
    assert len(points) == 9
    expected = (4.1 / 4.0 - 1) * 100
    assert points[0]["value"] == pytest.approx(expected)


def test_run_rebase100_transform(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "rebase100")

    assert points[0]["value"] == pytest.approx(100.0)
    assert points[-1]["value"] == pytest.approx(4.9 / 4.0 * 100)


def test_run_ma_transform(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "ma:3")

    assert len(points) == 10
    assert points[2]["value"] == pytest.approx((4.0 + 4.1 + 4.2) / 3)


def test_run_ratio_transform(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "ratio")

    assert len(points) == 9
    assert points[0]["value"] == pytest.approx(4.1 / 4.0)


def test_run_rolling_corr_requires_two_series(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    with pytest.raises(QueryError):
        query.run("fred:DGS10", "2024-01-01:2024-01-10", "rolling_corr:3")


def test_run_rolling_corr_two_series(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10 - fred:DGS2", "2024-01-01:2024-01-10", "rolling_corr:3")

    # both series are perfectly linear, so rolling correlation should be ~1
    assert len(points) > 0
    assert all(v["value"] == pytest.approx(1.0, abs=1e-6) for v in points)


def test_run_unknown_series_returns_empty(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    points = query.run("fred:UNKNOWN", "2024-01-01:2024-01-10", "none")
    assert points == []


def test_run_invalid_expression_raises(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    with pytest.raises(QueryError):
        query.run("__import__('os')", "2024-01-01:2024-01-10", "none")


def test_run_unknown_transform_raises(archive_root: Path) -> None:
    query = ArchiveQuery(archive_root)
    with pytest.raises(QueryError):
        query.run("fred:DGS10", "2024-01-01:2024-01-10", "bogus")


def test_run_resamples_when_above_threshold(archive_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.archive.query as query_module

    monkeypatch.setattr(query_module, "MAX_POINTS_BEFORE_RESAMPLE", 5)
    monkeypatch.setattr(query_module, "TARGET_POINTS", 2)

    query = ArchiveQuery(archive_root)
    points = query.run("fred:DGS10", "2024-01-01:2024-01-10", "none")

    assert 0 < len(points) <= 5


def test_run_concurrent_queries_do_not_corrupt_results(archive_root: Path) -> None:
    # Regression test: _load_series must use its own duckdb connection per call.
    # A shared module-level connection corrupts/returns None results under concurrent
    # access, since FastAPI runs sync endpoints across multiple threadpool threads.
    from concurrent.futures import ThreadPoolExecutor

    query = ArchiveQuery(archive_root)

    def run_query(_: int) -> list[dict]:
        return query.run("fred:DGS10", "2024-01-01:2024-01-10", "none")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run_query, range(50)))

    for points in results:
        assert len(points) == 10
        assert points[0]["value"] == pytest.approx(4.0)
