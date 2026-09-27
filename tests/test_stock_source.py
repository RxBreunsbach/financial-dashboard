from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.sources.stock import StockSource


def _fake_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [900.0, 910.0],
            "High": [915.0, 920.0],
            "Low": [895.0, 905.0],
            "Close": [905.0, 918.0],
            "Volume": [1_000_000, 1_200_000],
        },
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date"),
    )


def test_fetch_history_shapes_ohlcv_dataframe() -> None:
    source = StockSource("stock:NVDA", ticker="NVDA")
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _fake_history()

    with patch("app.sources.stock.yf.Ticker", return_value=mock_ticker) as mock_ticker_cls:
        df = source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

    mock_ticker_cls.assert_called_once_with("NVDA")
    assert list(df.columns) == ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert (df["series_id"] == "stock:NVDA").all()
    assert df["value"].tolist() == [905.0, 918.0]
    assert df["volume"].tolist() == [1_000_000, 1_200_000]


def test_fetch_history_empty_history_returns_empty_dataframe() -> None:
    source = StockSource("stock:NVDA", ticker="NVDA")
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()

    with patch("app.sources.stock.yf.Ticker", return_value=mock_ticker):
        df = source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

    assert df.empty
    assert list(df.columns) == ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]


def test_ticker_symbol_falls_back_to_series_id_suffix() -> None:
    source = StockSource("stock:AAPL")
    assert source._ticker_symbol() == "AAPL"
