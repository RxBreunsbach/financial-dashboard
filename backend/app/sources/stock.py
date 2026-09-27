"""Stock price history source plugin (Yahoo Finance via yfinance)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import yfinance as yf

from app.sources.base import SeriesMetadata, Source

OHLCV_COLUMNS = ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]


class StockSource(Source):
    """Fetches daily OHLCV history for a ticker, e.g. series_id="stock:NVDA"."""

    def _ticker_symbol(self) -> str:
        return str(self.params.get("ticker") or self.series_id.partition(":")[2])

    def fetch_history(self, start: datetime, end: datetime) -> pd.DataFrame:
        history = yf.Ticker(self._ticker_symbol()).history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
        )
        if history.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        history = history.reset_index()
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(history["Date"], utc=True),
                "series_id": self.series_id,
                "value": history["Close"],
                "open": history["Open"],
                "high": history["High"],
                "low": history["Low"],
                "close": history["Close"],
                "volume": history["Volume"],
            }
        )
        return df.reset_index(drop=True)

    def get_metadata(self) -> SeriesMetadata:
        info = yf.Ticker(self._ticker_symbol()).info
        return SeriesMetadata(
            source="stock",
            series_id=self.series_id,
            name=info.get("longName", self._ticker_symbol()),
            units="USD",
            frequency="daily",
        )
