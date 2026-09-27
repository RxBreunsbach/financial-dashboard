from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.archive.writer import ArchiveWriter


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    dates = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    df = pd.DataFrame({"timestamp": dates, "series_id": "fred:DGS10", "value": [4.0, 4.1, 4.2, 4.3, 4.4]})
    ArchiveWriter(tmp_path).write(df)

    import app.main as main_module

    monkeypatch.setattr(main_module.archive_query, "archive_root", tmp_path)
    return TestClient(main_module.app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_query_returns_points(client: TestClient) -> None:
    resp = client.get("/query", params={"series": "fred:DGS10", "range": "2024-01-01:2024-01-05"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["series"] == "fred:DGS10"
    assert body["transform"] == "none"
    assert len(body["points"]) == 5
    assert body["points"][0]["value"] == pytest.approx(4.0)


def test_query_invalid_transform_returns_400(client: TestClient) -> None:
    resp = client.get(
        "/query", params={"series": "fred:DGS10", "range": "2024-01-01:2024-01-05", "transform": "bogus"}
    )
    assert resp.status_code == 400


def test_get_dashboard_returns_spec(client: TestClient, tmp_path: Path) -> None:
    import app.main as main_module

    spec = {"title": "Rates", "timeRange": "1Y", "panels": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    (tmp_path / "rates.json").write_text(json.dumps(spec), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(main_module, "DASHBOARDS_ROOT", tmp_path)
        resp = client.get("/dashboards/rates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Rates"
    assert len(body["panels"]) == 3


def test_get_dashboard_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/dashboards/does-not-exist")
    assert resp.status_code == 404


def test_dashboard_path_rejects_invalid_names() -> None:
    from fastapi import HTTPException

    import app.main as main_module

    for bad_name in ("..", "../evil", "foo/bar", "foo.json", "foo bar"):
        with pytest.raises(HTTPException) as exc_info:
            main_module._dashboard_path(bad_name)
        assert exc_info.value.status_code == 400


def test_save_dashboard_writes_spec_and_round_trips(client: TestClient, tmp_path: Path) -> None:
    import app.main as main_module

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(main_module, "DASHBOARDS_ROOT", tmp_path)
        spec = {"title": "Test", "timeRange": "1Y", "panels": [{"id": "a", "type": "line", "series": "fred:DGS10"}]}

        put_resp = client.put("/dashboards/scratch", json=spec)
        assert put_resp.status_code == 200

        get_resp = client.get("/dashboards/scratch")
        assert get_resp.status_code == 200
        assert get_resp.json() == spec


def test_save_dashboard_requires_panels_list(client: TestClient, tmp_path: Path) -> None:
    import app.main as main_module

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(main_module, "DASHBOARDS_ROOT", tmp_path)
        resp = client.put("/dashboards/scratch", json={"title": "Test"})
        assert resp.status_code == 400
