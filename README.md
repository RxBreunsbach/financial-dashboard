# Financial Dashboard

A personal dashboard for visualizing current and historical financial data (stocks, bonds/rates via FRED, crypto), with all collected data archived permanently for later re-visualization.

## What It Does

1. **Collect** — Source plugins (`backend/app/sources/`) fetch historical data (FRED, Yahoo Finance, Coinbase); a background scheduler (`backend/app/scheduler.py`) periodically re-fetches each series per its cron schedule in `config/sources.yaml` (crypto every 15 minutes, FRED/stocks daily).
2. **Archive** — Every fetched row is appended to a permanent, source-agnostic Parquet archive; raw data is never modified or deleted.
3. **Query** — The `/query` API reads the archive with DuckDB, evaluates series expressions (e.g. `fred:DGS10 - fred:DGS2`), applies optional transforms, and resamples to a chart-friendly number of points.
4. **Visualize** — The frontend loads a dashboard spec (JSON) and renders each panel (Plotly line charts) in a `gridstack.js` grid layout, polling `/query` for every panel on a fixed interval so all panels refresh together.
5. **Edit** — An in-browser edit mode lets you drag/resize panels, add/remove/edit panels, and save the layout back to the dashboard's JSON file.

## File Locations

| Role                   | Path                                                            |
| ---------------------- | --------------------------------------------------------------- |
| Backend app entry      | `backend/app/main.py`                                           |
| Data source plugins    | `backend/app/sources/*.py`                                      |
| Archive writer/query   | `backend/app/archive/writer.py`, `backend/app/archive/query.py` |
| Backfill CLI           | `backend/app/cli.py`                                            |
| Series/schedule config | `config/sources.yaml`                                           |
| Data archive (output)  | `data/archive/<source>/<series>/<YYYY-MM>.parquet` (gitignored) |
| Dashboard specs        | `dashboards/*.json`                                             |
| Frontend engine        | `frontend/src/engine/`                                          |
| Frontend panel types   | `frontend/src/panels/`                                          |
| Secrets                | `.env` (gitignored, see `.env.example`)                         |
| Tests                  | `tests/`                                                        |

## API Endpoints

| Endpoint                 | Description                                              |
| ------------------------ | -------------------------------------------------------- |
| `GET /health`            | Liveness check                                           |
| `GET /query`             | `series`, `range`, `transform` params → resampled points |
| `GET /dashboards/{name}` | Load a dashboard spec from `dashboards/{name}.json`      |
| `PUT /dashboards/{name}` | Save a dashboard spec to `dashboards/{name}.json`        |

## Requirements

- Python 3.12+
- Node.js 20+ (Vite 8 requires 20.19+ or 22.12+)
- A free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) for the FRED plugin (stocks and crypto plugins need no key)
- Optional: a free [Finnhub API key](https://finnhub.io/register) — used to patch today's stock bar with a real-time quote when Yahoo Finance hasn't finalized the day's Close yet (Yahoo can leave Close/Open/High/Low null for a few hours after market close even though Volume is already posted)
- Dependencies listed in `pyproject.toml` (backend) and `frontend/package.json` (frontend)

## Setup

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env   # then fill in FRED_API_KEY (and optionally FINNHUB_API_KEY)

# Frontend
cd frontend
npm install
cd ..
```

## Usage

```powershell
# Backfill historical data into the archive (reads config/sources.yaml)
.\.venv\Scripts\backfill --start 2020-01-01

# Backfill just one newly added series, without re-fetching everything else
.\.venv\Scripts\backfill --start 2020-01-01 --series stock:URA

# Run both the backend and frontend dev servers together (Ctrl+C stops both)
.\.venv\Scripts\dev
```

Or run them separately in two terminals:

```powershell
# Backend API (http://localhost:8000)
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend

# Frontend dev server (http://localhost:5173)
cd frontend
npm run dev
```

Visit `http://localhost:5173/?dashboard=rates` or `http://localhost:5173/?dashboard=markets` to view the sample dashboards.

### Kiosk Mode

To open a dashboard in a headerless (no address bar/tabs) browser window, e.g. for a dedicated monitor, with the dev servers already running:

```powershell
.\.venv\Scripts\kiosk rates
```

Requires Chrome or Edge. Defaults to Chrome; pass `--browser edge` to use Edge instead. Pass a different dashboard name as the argument (defaults to `rates`), and optionally `--width`/`--height`.

### Fresh Start

To reset everything in one step — stopping any backend, frontend, or kiosk windows left over from a previous run, then starting the backend, frontend, and a kiosk window for every dashboard in `dashboards/`:

```powershell
.\.venv\Scripts\fresh_start
```

Ctrl+C stops the backend and frontend (kiosk windows stay open, since they're independent browser processes).

### Running Tests

```powershell
.\.venv\Scripts\pytest -q
```
