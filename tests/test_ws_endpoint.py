from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient


class _FakeSource:
    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id

    async def stream(self):
        for i in range(2):
            yield {
                "timestamp": pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(seconds=i),
                "series_id": self.series_id,
                "value": float(i),
            }
            await asyncio.sleep(0)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.live as live_module
    import app.main as main_module

    monkeypatch.setitem(live_module.REGISTRY, "fake", _FakeSource)
    monkeypatch.setattr(main_module.live_manager.writer, "archive_root", tmp_path)
    return TestClient(main_module.app)


def test_ws_subscribe_receives_live_points(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "subscribe", "series_id": "fake:XYZ"})
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert first == {"series_id": "fake:XYZ", "timestamp": "2024-01-01T00:00:00+00:00", "value": 0.0}
    assert second["value"] == 1.0
