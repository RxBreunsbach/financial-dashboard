from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import app.scheduler as scheduler_module


class _FakeSource:
    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id
        self.params = params
        self.calls: list[tuple] = []

    def fetch_history(self, start, end) -> pd.DataFrame:
        self.calls.append((start, end))
        return pd.DataFrame(
            {"timestamp": [pd.Timestamp("2024-01-01", tz="UTC")], "series_id": [self.series_id], "value": [1.0]}
        )


class _FailingSource:
    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id

    def fetch_history(self, start, end) -> pd.DataFrame:
        raise RuntimeError("boom")


FAKE_ENTRIES = [
    {"series_id": "fred:DGS10", "plugin": "fake", "schedule": "0 6 * * *"},
    {"series_id": "stock:URA", "plugin": "fake", "schedule": "0 21 * * 1-5"},
    {"series_id": "no:schedule", "plugin": "fake"},  # no "schedule" key -> should not get a job
]


@pytest.fixture(autouse=True)
def _fake_config_and_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(scheduler_module, "load_sources_config", lambda: FAKE_ENTRIES)
    monkeypatch.setitem(scheduler_module.REGISTRY, "fake", _FakeSource)
    monkeypatch.setattr(scheduler_module, "ARCHIVE_ROOT", tmp_path)


def test_create_scheduler_adds_one_job_per_scheduled_entry() -> None:
    scheduler = scheduler_module.create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {"fred:DGS10", "stock:URA"}


def test_run_job_writes_to_archive(tmp_path: Path) -> None:
    scheduler_module._run_job({"series_id": "fred:DGS10", "plugin": "fake", "schedule": "0 6 * * *"})

    result = pd.read_parquet(tmp_path / "fred" / "DGS10" / "2024-01.parquet")
    assert len(result) == 1


def test_run_job_swallows_source_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(scheduler_module.REGISTRY, "failing", _FailingSource)

    # Must not raise: a failing source shouldn't crash the scheduler.
    scheduler_module._run_job({"series_id": "fred:BROKEN", "plugin": "failing", "schedule": "0 6 * * *"})

    assert not (tmp_path / "fred" / "BROKEN").exists()
