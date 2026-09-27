"""Registry mapping plugin names (from config/sources.yaml) to Source classes."""

from app.sources.base import Source
from app.sources.coinbase import CoinbaseSource
from app.sources.fred import FredSource
from app.sources.stock import StockSource

REGISTRY: dict[str, type[Source]] = {
    "fred": FredSource,
    "stock": StockSource,
    "coinbase": CoinbaseSource,
    "crypto": CoinbaseSource,  # alias: lets ad hoc "crypto:<product>" live subscriptions resolve without config
}
