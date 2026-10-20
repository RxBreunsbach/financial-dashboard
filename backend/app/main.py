"""FastAPI app entry point. Endpoints are added in later build steps."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.archive.query import ArchiveQuery, QueryError
from app.config import ARCHIVE_ROOT, DASHBOARDS_ROOT
from app.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Financial Dashboard", lifespan=lifespan)
archive_query = ArchiveQuery(ARCHIVE_ROOT)

# Dev-only: allow the Vite dev server to call the API cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "PUT"],
    allow_headers=["*"],
)

DASHBOARD_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _dashboard_path(name: str) -> Path:
    if not DASHBOARD_NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid dashboard name: {name!r}")
    return DASHBOARDS_ROOT / f"{name}.json"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboards/{name}")
def get_dashboard(name: str) -> dict:
    path = _dashboard_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dashboard not found: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/dashboards/{name}")
def save_dashboard(name: str, spec: dict = Body(...)) -> dict:
    if "panels" not in spec or not isinstance(spec["panels"], list):
        raise HTTPException(status_code=400, detail="Dashboard spec must include a 'panels' list")
    path = _dashboard_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    return spec


class QueryPoint(BaseModel):
    timestamp: str
    value: float


class QueryResponse(BaseModel):
    series: str
    range: str
    transform: str
    points: list[QueryPoint]


@app.get("/query", response_model=QueryResponse)
def query(
    series: str = Query(..., description="Series id or expression, e.g. 'fred:DGS10 - fred:DGS2'"),
    time_range: str = Query(
        "1Y", alias="range", description="1D, 1W, 1M, YTD, 1Y, 5Y, Max, or 'start:end' ISO dates"
    ),
    transform: str = Query("none", description="none, pct_change, yoy, rebase100, ma:<n>, ratio, rolling_corr:<n>"),
) -> QueryResponse:
    try:
        points = archive_query.run(series, time_range, transform)
    except QueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryResponse(series=series, range=time_range, transform=transform, points=points)
