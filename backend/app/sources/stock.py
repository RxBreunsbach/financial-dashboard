"""Stock price history source plugin (Yahoo Finance via yfinance)."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

from app.sources.base import SeriesMetadata, Source

OHLCV_COLUMNS = ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

logger = logging.getLogger(__name__)


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
        df = df.reset_index(drop=True)
        self._patch_unfinalized_latest_bar(df)
        return df

    def _patch_unfinalized_latest_bar(self, df: pd.DataFrame) -> None:
        """Yahoo sometimes publishes today's bar with Volume but null OHLC/Close
        for a few hours after close. Patch that row in place with Finnhub's
        free real-time quote, if a key is configured, rather than leaving gaps."""
        if df.empty or not pd.isna(df.loc[df.index[-1], "value"]):
            return
        api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            return

        try:
            resp = requests.get(
                FINNHUB_QUOTE_URL,
                params={"symbol": self._ticker_symbol(), "token": api_key},
                timeout=10,
            )
            resp.raise_for_status()
            quote = resp.json()
            price = quote.get("c")
            if not price:
                return
        except (requests.RequestException, ValueError):
            logger.exception("Finnhub quote patch failed for %s", self.series_id)
            return

        last = df.index[-1]
        df.loc[last, ["value", "close"]] = price
        for field, key in (("open", "o"), ("high", "h"), ("low", "l")):
            if quote.get(key):
                df.loc[last, field] = quote[key]

    def get_metadata(self) -> SeriesMetadata:
        info = yf.Ticker(self._ticker_symbol()).info
        return SeriesMetadata(
            source="stock",
            series_id=self.series_id,
            name=info.get("longName", self._ticker_symbol()),
            units="USD",
            frequency="daily",
        )
