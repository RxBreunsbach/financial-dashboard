from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.sources.coinbase import CoinbaseSource


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def __aiter__(self):
        for message in self._messages:
            yield message


class _FakeConnectCtx:
    def __init__(self, ws: _FakeWebSocket) -> None:
        self._ws = ws

    async def __aenter__(self) -> _FakeWebSocket:
        return self._ws

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def test_fetch_history_shapes_ohlcv_dataframe() -> None:
    source = CoinbaseSource("crypto:BTC-USD")
    # Coinbase candles are [time, low, high, open, close, volume], newest first.
    fake_rows = [
        [1704240000, 64000.0, 65000.0, 64500.0, 64800.0, 12.5],
        [1704153600, 63000.0, 64000.0, 63500.0, 63900.0, 10.1],
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = fake_rows

    with patch("app.sources.coinbase.requests.get", return_value=mock_response) as mock_get:
        df = source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 5, tzinfo=timezone.utc),
        )

    assert list(df.columns) == ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["value"].tolist() == [63900.0, 64800.0]  # sorted ascending by timestamp
    assert (df["series_id"] == "crypto:BTC-USD").all()

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["granularity"] == 86400


def test_fetch_history_empty_response_returns_empty_dataframe() -> None:
    source = CoinbaseSource("crypto:BTC-USD")
    mock_response = MagicMock()
    mock_response.json.return_value = []

    with patch("app.sources.coinbase.requests.get", return_value=mock_response):
        df = source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 5, tzinfo=timezone.utc),
        )

    assert df.empty
    assert list(df.columns) == ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]


def test_fetch_history_chunks_long_ranges() -> None:
    # Coinbase caps each request at 300 daily candles; a multi-year range must be split.
    source = CoinbaseSource("crypto:BTC-USD")
    mock_response = MagicMock()
    mock_response.json.return_value = [[1704153600, 63000.0, 64000.0, 63500.0, 63900.0, 10.1]]

    with patch("app.sources.coinbase.requests.get", return_value=mock_response) as mock_get:
        df = source.fetch_history(
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 9, 25, tzinfo=timezone.utc),
        )

    assert mock_get.call_count > 1
    assert not df.empty


def test_stream_yields_ticker_prices_and_ignores_other_messages(monkeypatch) -> None:
    ws = _FakeWebSocket(
        [
            json.dumps({"type": "subscriptions"}),
            json.dumps({"type": "ticker", "price": "65000.5"}),
            json.dumps({"type": "ticker", "price": "65010.25"}),
        ]
    )
    monkeypatch.setattr("app.sources.coinbase.websockets.connect", lambda url: _FakeConnectCtx(ws))

    source = CoinbaseSource("crypto:BTC-USD")

    async def collect() -> list[dict]:
        return [point async for point in source.stream()]

    points = asyncio.run(collect())

    assert [p["value"] for p in points] == [65000.5, 65010.25]
    assert all(p["series_id"] == "crypto:BTC-USD" for p in points)
    assert json.loads(ws.sent[0])["product_ids"] == ["BTC-USD"]
