"""Coinbase source plugin: crypto ticker history (no API key required)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import requests

from app.sources.base import SeriesMetadata, Source

CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
DAILY_GRANULARITY_SECONDS = 86400
MAX_CANDLES_PER_REQUEST = 300  # Coinbase rejects requests spanning more candles than this
HEADERS = {"User-Agent": "financial-dashboard/0.1"}
OHLCV_COLUMNS = ["timestamp", "series_id", "value", "open", "high", "low", "close", "volume"]


class CoinbaseSource(Source):
    """Fetches a Coinbase product's daily candles, e.g. series_id="crypto:BTC-USD"."""

    def _product_id(self) -> str:
        return str(self.params.get("product_id") or self.series_id.partition(":")[2])

    def fetch_history(self, start: datetime, end: datetime) -> pd.DataFrame:
        chunk_span = timedelta(seconds=DAILY_GRANULARITY_SECONDS * MAX_CANDLES_PER_REQUEST)
        chunks = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + chunk_span, end)
            chunks.append(self._fetch_candles(chunk_start, chunk_end))
            chunk_start = chunk_end

        if not chunks:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        df = pd.concat(chunks, ignore_index=True)
        return df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

    def _fetch_candles(self, start: datetime, end: datetime) -> pd.DataFrame:
        resp = requests.get(
            CANDLES_URL.format(product_id=self._product_id()),
            params={"start": start.isoformat(), "end": end.isoformat(), "granularity": DAILY_GRANULARITY_SECONDS},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["series_id"] = self.series_id
        df["value"] = df["close"]
        return df[OHLCV_COLUMNS]

    def get_metadata(self) -> SeriesMetadata:
        return SeriesMetadata(
            source="crypto",
            series_id=self.series_id,
            name=self._product_id(),
            units="USD",
            frequency="daily",
        )
