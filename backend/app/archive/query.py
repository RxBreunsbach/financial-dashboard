"""DuckDB-backed queries over the Parquet archive: series expressions, time ranges, resampling, transforms."""

from __future__ import annotations

import ast
import operator
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd

TARGET_POINTS = 1500
MAX_POINTS_BEFORE_RESAMPLE = 2000

SERIES_ID_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*:[a-zA-Z0-9_.\-]+")
EXPRESSION_ALLOWED_PATTERN = re.compile(r"^[\w\s:.\-+*/()]+$")

RELATIVE_RANGE_DAYS: dict[str, float | None] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "1Y": 365,
    "5Y": 365 * 5,
    "MAX": None,
}

_BINOPS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARYOPS: dict[type, object] = {ast.USub: operator.neg, ast.UAdd: operator.pos}


class QueryError(ValueError):
    """Raised for invalid series expressions, time ranges, or transforms."""


def resolve_time_range(time_range: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Resolve a keyword (1D/1W/1M/YTD/1Y/5Y/Max) or explicit "start:end" ISO range to UTC datetimes."""
    now = now or datetime.now(timezone.utc)
    key = time_range.strip().upper()

    if key == "YTD":
        return datetime(now.year, 1, 1, tzinfo=timezone.utc), now
    if key in RELATIVE_RANGE_DAYS:
        days = RELATIVE_RANGE_DAYS[key]
        start = now - timedelta(days=days) if days is not None else datetime(1900, 1, 1, tzinfo=timezone.utc)
        return start, now
    if ":" in time_range:
        start_str, _, end_str = time_range.partition(":")
        start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc) if end_str else now
        return start, end
    raise QueryError(f"Unrecognized time range: {time_range!r}")


def _series_ids_in(expression: str) -> list[str]:
    seen: dict[str, None] = {}
    for match in SERIES_ID_PATTERN.finditer(expression):
        seen.setdefault(match.group(0), None)
    return list(seen)


def _eval_ast(node: ast.AST, values: dict[str, pd.Series]) -> pd.Series | float:
    """Evaluate a restricted arithmetic AST (+ - * / and unary +/-, names, numbers only)."""
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, values)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_ast(node.left, values), _eval_ast(node.right, values))  # type: ignore[operator]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_ast(node.operand, values))  # type: ignore[operator]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    raise QueryError("Unsupported syntax in series expression")


def _year_over_year(timestamps: pd.Series, values: pd.Series) -> pd.Series:
    df = pd.DataFrame({"timestamp": timestamps, "value": values}).sort_values("timestamp")
    shifted = df.rename(columns={"value": "value_prior"}).copy()
    shifted["timestamp"] = shifted["timestamp"] + pd.Timedelta(days=365)
    merged = pd.merge_asof(df, shifted, on="timestamp", direction="backward", tolerance=pd.Timedelta(days=10))
    return (merged["value"] / merged["value_prior"] - 1) * 100


def _resample(df: pd.DataFrame, start: datetime, end: datetime, target_points: int | None = None) -> pd.DataFrame:
    """Downsample to roughly `target_points` rows using DuckDB's time_bucket, once above the threshold."""
    if len(df) <= MAX_POINTS_BEFORE_RESAMPLE:
        return df
    if target_points is None:
        target_points = TARGET_POINTS

    total_seconds = max((end - start).total_seconds(), 1)
    bucket_seconds = max(int(total_seconds / target_points), 1)

    con = duckdb.connect()
    try:
        con.register("points", df)
        resampled = con.execute(
            f"""
            SELECT time_bucket(INTERVAL '{bucket_seconds} seconds', timestamp) AS timestamp, avg(value) AS value
            FROM points
            GROUP BY 1
            ORDER BY 1
            """
        ).df()
    finally:
        con.close()

    resampled["timestamp"] = pd.to_datetime(resampled["timestamp"], utc=True)
    return resampled


class ArchiveQuery:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = Path(archive_root)

    def run(self, series_expr: str, time_range: str, transform: str = "none") -> list[dict]:
        start, end = resolve_time_range(time_range)
        series_ids = _series_ids_in(series_expr)
        if not series_ids:
            raise QueryError(f"No series ids found in expression: {series_expr!r}")

        aligned = self._load_aligned(series_ids, start, end)
        if aligned.empty:
            return []

        values = self._evaluate_expression(series_expr, aligned, series_ids)
        values = self._apply_transform(transform, series_ids, aligned, values)

        result = pd.DataFrame({"timestamp": aligned["timestamp"], "value": values}).dropna(subset=["value"])
        result = _resample(result, start, end)
        return [{"timestamp": ts.isoformat(), "value": float(v)} for ts, v in zip(result["timestamp"], result["value"])]

    def _load_series(self, series_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        source, _, series = series_id.partition(":")
        partition_dir = self.archive_root / source / series
        if not partition_dir.exists() or not any(partition_dir.glob("*.parquet")):
            empty = pd.DataFrame({"timestamp": pd.Series(dtype="datetime64[ns, UTC]"), series_id: pd.Series(dtype="float64")})
            return empty

        glob_pattern = (partition_dir / "*.parquet").as_posix()
        con = duckdb.connect()
        try:
            df = con.execute(
                f"""
                SELECT timestamp, value
                FROM read_parquet('{glob_pattern}')
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp
                """,
                [start, end],
            ).df()
        finally:
            con.close()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.rename(columns={"value": series_id})

    def _load_aligned(self, series_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        combined = self._load_series(series_ids[0], start, end)
        for series_id in series_ids[1:]:
            combined = combined.merge(self._load_series(series_id, start, end), on="timestamp", how="outer")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        combined[series_ids] = combined[series_ids].ffill()  # align mixed-frequency series
        return combined

    def _evaluate_expression(self, expression: str, aligned: pd.DataFrame, series_ids: list[str]) -> pd.Series:
        if not EXPRESSION_ALLOWED_PATTERN.match(expression):
            raise QueryError(f"Invalid characters in series expression: {expression!r}")

        safe_names = {sid: f"_s{i}" for i, sid in enumerate(series_ids)}
        safe_expression = expression
        for sid, name in sorted(safe_names.items(), key=lambda kv: -len(kv[0])):
            safe_expression = safe_expression.replace(sid, name)

        try:
            tree = ast.parse(safe_expression, mode="eval")
        except SyntaxError as exc:
            raise QueryError(f"Could not parse series expression: {expression!r}") from exc

        result = _eval_ast(tree, {name: aligned[sid] for sid, name in safe_names.items()})
        return result if isinstance(result, pd.Series) else pd.Series(float(result), index=aligned.index)

    def _apply_transform(
        self, transform: str, series_ids: list[str], aligned: pd.DataFrame, values: pd.Series
    ) -> pd.Series:
        name, _, arg = transform.partition(":")
        name = name.strip().lower()

        if name in ("", "none"):
            return values
        if name == "pct_change":
            return values.pct_change() * 100
        if name == "ratio":
            return values / values.shift(1)
        if name == "rebase100":
            non_null = values.dropna()
            first = non_null.iloc[0] if not non_null.empty else float("nan")
            return values / first * 100
        if name == "ma":
            return values.rolling(int(arg), min_periods=1).mean()
        if name == "yoy":
            return _year_over_year(aligned["timestamp"], values)
        if name == "rolling_corr":
            if len(series_ids) != 2:
                raise QueryError("rolling_corr requires exactly two series ids")
            a, b = (aligned[sid] for sid in series_ids)
            return a.rolling(int(arg), min_periods=2).corr(b)
        raise QueryError(f"Unknown transform: {transform!r}")
