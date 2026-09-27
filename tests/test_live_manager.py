from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
import pytest

import app.live as live_module
from app.archive.writer import ArchiveWriter
from app.live import LiveManager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


class _FakeSource:
    """Yields 3 points then stops, so background tasks finish on their own."""

    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id

    async def stream(self):
        for i in range(3):
            yield {
                "timestamp": pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(seconds=i),
                "series_id": self.series_id,
                "value": float(i),
            }
            await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def _fake_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(live_module.REGISTRY, "fake", _FakeSource)


def test_subscribe_broadcasts_points_and_archives_them(tmp_path: Path) -> None:
    async def run() -> _FakeWebSocket:
        manager = LiveManager(ArchiveWriter(tmp_path))
        ws = _FakeWebSocket()
        await manager.subscribe("fake:XYZ", ws)
        await asyncio.sleep(0.05)
        await manager.unsubscribe("fake:XYZ", ws)
        await asyncio.sleep(0)
        return ws

    ws = asyncio.run(run())

    assert len(ws.sent) == 3
    assert ws.sent[0]["series_id"] == "fake:XYZ"
    assert [m["value"] for m in ws.sent] == [0.0, 1.0, 2.0]

    archived = pd.read_parquet(tmp_path / "fake" / "XYZ" / "2024-01.parquet")
    assert len(archived) == 3


def test_unsubscribe_last_listener_cancels_task(tmp_path: Path) -> None:
    async def run() -> LiveManager:
        manager = LiveManager(ArchiveWriter(tmp_path))
        ws = _FakeWebSocket()
        await manager.subscribe("fake:ABC", ws)
        assert "fake:ABC" in manager._tasks
        await manager.unsubscribe("fake:ABC", ws)
        return manager

    manager = asyncio.run(run())
    assert "fake:ABC" not in manager._tasks
    assert "fake:ABC" not in manager._subscribers


def test_unknown_source_prefix_logs_and_returns(tmp_path: Path) -> None:
    async def run() -> _FakeWebSocket:
        manager = LiveManager(ArchiveWriter(tmp_path))
        ws = _FakeWebSocket()
        await manager.subscribe("bogus:XYZ", ws)
        await asyncio.sleep(0.05)
        return ws

    ws = asyncio.run(run())
    assert ws.sent == []
