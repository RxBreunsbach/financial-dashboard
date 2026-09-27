"""Source base class: the plugin contract for all data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class SeriesMetadata:
    source: str
    series_id: str
    name: str
    units: str
    frequency: str
    last_fetched: datetime | None = None


class Source(ABC):
    """Base class for a data source plugin, scoped to one series.

    Subclasses fetch data for `series_id` (e.g. "fred:DGS10") and return it
    in the archive's canonical shape: columns `timestamp` (UTC, tz-aware),
    `series_id`, `value`, and optionally `open, high, low, close, volume`.
    """

    def __init__(self, series_id: str, **params: object) -> None:
        self.series_id = series_id
        self.params = params

    @abstractmethod
    def fetch_history(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch historical data for this series between start and end (UTC)."""
        raise NotImplementedError

    def get_metadata(self) -> SeriesMetadata:
        """Return metadata describing this series. Override for real metadata."""
        raise NotImplementedError

    async def stream(self):
        """Optional: yield live updates for this series. Override to support streaming."""
        raise NotImplementedError
        yield  # pragma: no cover - marks this method as an async generator
