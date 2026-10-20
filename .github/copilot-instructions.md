# Copilot Instructions

## Goal

A personal dashboard showing current and historical financial data (stocks, bonds/rates, FRED economic data, crypto, and future sources). All collected data is archived permanently so it can be re-visualized later. Developed on Windows, must run unchanged on macOS (Apple Silicon).

## Tech stack

- Backend: Python 3.12+, FastAPI, APScheduler, pandas, DuckDB, PyArrow, python-dotenv
- Frontend: Vite + plain JavaScript (ES modules, no framework unless requested), Plotly for general charts, TradingView Lightweight Charts for price/candlestick charts, gridstack.js for layout
- Tests: pytest (backend), keep tests small and fast

## Folder structure

```
backend/
  app/main.py            # FastAPI app: REST /query, /series, /dashboards
  app/sources/base.py    # Source base class (plugin contract)
  app/sources/*.py       # one file per data source plugin
  app/archive/writer.py  # append-only Parquet writer
  app/archive/query.py   # DuckDB queries, resampling, transforms
  app/scheduler.py       # runs collectors per config/sources.yaml
config/sources.yaml      # declares which series to collect and how often
dashboards/*.json        # dashboard spec files (layout + panels)
frontend/src/engine/     # dashboard loader, time controls
frontend/src/panels/     # one module per panel type (registry)
data/archive/            # Parquet archive (gitignored)
tests/
```

## Core rules

1. Cross-platform: use `pathlib` for all paths, never hardcode absolute paths or OS-specific separators. Scripts must work in both PowerShell and zsh, or be provided as Python entry points.
2. Secrets live only in `.env` (gitignored). Provide `.env.example` with placeholder names.
3. The archive is append-only raw data. Never modify or delete archived records. Derived values (transforms, resampling) are computed at query time, never stored over raw data.
4. Data sources are plugins. The dashboard and archive must never contain source-specific logic.
5. Dashboards are data, not code. New views are created by adding/editing JSON in `dashboards/`, not by writing new frontend code.
6. Work in small, reviewable steps. Do not implement features beyond what the current request asks.

## Source plugin contract

Every plugin subclasses `Source` and returns a pandas DataFrame with columns:
`timestamp` (UTC, tz-aware), `series_id` (e.g. `fred:DGS10`, `stock:NVDA`), `value` (float), and optionally `open, high, low, close, volume`.
Methods: `fetch_history(start, end)`. All sources are refreshed periodically by `app/scheduler.py` per their configured cron schedule in `config/sources.yaml` (fast-moving sources like crypto use a short interval, e.g. every 15 minutes); there is no push-based live streaming.
Each series also has metadata: source, name, units, frequency, last_fetched.

## Archive layout

Parquet files partitioned as `data/archive/<source>/<series>/<YYYY-MM>.parquet`, plus a metadata catalog. DuckDB reads the Parquet files directly; no database server.

## Query API

`/query` accepts: series ids (including expressions like `fred:DGS10 - fred:DGS2`), time range (1D, 1W, 1M, YTD, 1Y, 5Y, Max or explicit dates), optional transform (`none`, `pct_change`, `yoy`, `rebase100`, `ma:<n>`, `ratio`, `rolling_corr:<n>`), and returns data auto-resampled to roughly 1,000-2,000 points using DuckDB `time_bucket`. Mixed-frequency series align with forward-fill when requested.

## Dashboard spec (dashboards/\*.json)

Fields: `title`, `timeRange` (global default), `variables` (e.g. `symbol` dropdown, referenced as `$symbol`), and `panels`. Each panel has `id`, `type`, grid position `x, y, w, h`, `series`, and optional `transform`, `timeRange`, `title`.

## Panel registry (frontend)

Each panel type module exports `render(el, data, options)`, `update(points)`, and `destroy()`, and registers under its type name. Initial types: line, candlestick, bar, stat, table, scatter, heatmap. The frontend polls `/query` for every panel on a fixed interval (`REFRESH_INTERVAL_MS` in `main.js`) so all panels refresh together.

## Build order

1. Scaffold + FRED plugin + archive writer + backfill CLI
2. Stock history plugin (yfinance or Tiingo)
3. `/query` endpoint with transforms and resampling
4. Frontend engine, line panel, global time selector, sample `dashboards/rates.json`
5. Scheduled background refresh (FRED/stocks/Coinbase) via APScheduler cron jobs per `config/sources.yaml`
6. In-browser edit mode (gridstack drag/resize, panel editor, save to JSON)
