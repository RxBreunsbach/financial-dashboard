"""FRED (Federal Reserve Economic Data) source plugin."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests

from app.sources.base import SeriesMetadata, Source

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
INFO_URL = "https://api.stlouisfed.org/fred/series"


class FredSource(Source):
    """Fetches a single FRED series, e.g. series_id="fred:DGS10"."""

    def _fred_series_id(self) -> str:
        return str(self.params.get("fred_series_id") or self.series_id.partition(":")[2])

    def _api_key(self) -> str:
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            raise RuntimeError("FRED_API_KEY is not set (see .env.example)")
        return api_key

    def fetch_history(self, start: datetime, end: datetime) -> pd.DataFrame:
        resp = requests.get(
            BASE_URL,
            params={
                "series_id": self._fred_series_id(),
                "api_key": self._api_key(),
                "file_type": "json",
                "observation_start": start.strftime("%Y-%m-%d"),
                "observation_end": end.strftime("%Y-%m-%d"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        observations = resp.json()["observations"]

        df = pd.DataFrame(observations)
        if df.empty:
            return pd.DataFrame(columns=["timestamp", "series_id", "value"])

        df = df[df["value"] != "."]  # FRED marks missing observations as "."
        df["timestamp"] = pd.to_datetime(df["date"], utc=True)
        df["value"] = df["value"].astype(float)
        df["series_id"] = self.series_id
        return df[["timestamp", "series_id", "value"]].reset_index(drop=True)

    def get_metadata(self) -> SeriesMetadata:
        resp = requests.get(
            INFO_URL,
            params={
                "series_id": self._fred_series_id(),
                "api_key": self._api_key(),
                "file_type": "json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        info = resp.json()["seriess"][0]
        return SeriesMetadata(
            source="fred",
            series_id=self.series_id,
            name=info["title"],
            units=info["units"],
            frequency=info["frequency"],
        )
