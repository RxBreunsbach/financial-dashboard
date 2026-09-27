from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.sources.fred import FredSource

OBSERVATIONS_RESPONSE = {
    "observations": [
        {"date": "2024-01-02", "value": "4.1"},
        {"date": "2024-01-03", "value": "."},  # missing observation
        {"date": "2024-01-04", "value": "4.2"},
    ]
}


@pytest.fixture(autouse=True)
def _fred_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test-key")


def test_fetch_history_drops_missing_and_shapes_dataframe() -> None:
    source = FredSource("fred:DGS10", fred_series_id="DGS10")
    mock_response = MagicMock()
    mock_response.json.return_value = OBSERVATIONS_RESPONSE

    with patch("app.sources.fred.requests.get", return_value=mock_response) as mock_get:
        df = source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

    assert list(df.columns) == ["timestamp", "series_id", "value"]
    assert len(df) == 2
    assert (df["series_id"] == "fred:DGS10").all()
    assert df["value"].tolist() == [4.1, 4.2]

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["series_id"] == "DGS10"


def test_fetch_history_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    source = FredSource("fred:DGS10", fred_series_id="DGS10")

    with pytest.raises(RuntimeError):
        source.fetch_history(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )
