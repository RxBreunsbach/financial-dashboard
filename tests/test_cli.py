from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

import app.cli as cli_module


class _FakeSource:
    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id

    def fetch_history(self, start: datetime, end: datetime) -> pd.DataFrame:
        return pd.DataFrame(
            {"timestamp": [pd.Timestamp("2024-01-01", tz="UTC")], "series_id": [self.series_id], "value": [1.0]}
        )


FAKE_ENTRIES = [
    {"series_id": "fred:DGS10", "plugin": "fake", "schedule": "0 6 * * *"},
    {"series_id": "stock:URA", "plugin": "fake", "schedule": "0 21 * * 1-5"},
]


@pytest.fixture(autouse=True)
def _fake_config_and_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_module, "load_sources_config", lambda: FAKE_ENTRIES)
    monkeypatch.setitem(cli_module.REGISTRY, "fake", _FakeSource)
    monkeypatch.setattr(cli_module, "ARCHIVE_ROOT", tmp_path)


def test_backfill_with_no_filter_fetches_all_series(tmp_path: Path) -> None:
    cli_module.backfill(datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 2, tzinfo=timezone.utc))

    assert (tmp_path / "fred" / "DGS10" / "2024-01.parquet").exists()
    assert (tmp_path / "stock" / "URA" / "2024-01.parquet").exists()


def test_backfill_with_series_filter_only_fetches_that_series(tmp_path: Path) -> None:
    cli_module.backfill(
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 2, tzinfo=timezone.utc),
        series_ids={"stock:URA"},
    )

    assert not (tmp_path / "fred" / "DGS10" / "2024-01.parquet").exists()
    assert (tmp_path / "stock" / "URA" / "2024-01.parquet").exists()


def test_backfill_with_unknown_series_raises() -> None:
    with pytest.raises(SystemExit):
        cli_module.backfill(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 2, tzinfo=timezone.utc),
            series_ids={"stock:DOES_NOT_EXIST"},
        )
