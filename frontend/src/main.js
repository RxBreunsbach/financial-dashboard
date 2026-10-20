import "gridstack/dist/gridstack.min.css";
import { GridStack } from "gridstack";
import "./style.css";
import { fetchSeries } from "./engine/apiClient.js";
import {
  loadDashboard,
  substituteVariables,
} from "./engine/dashboardLoader.js";
import { createEditMode } from "./engine/editMode.js";
import { addPanelWidget } from "./engine/gridWidgets.js";
import { KNOWN_SERIES } from "./engine/knownSeries.js";
import { createTimeRangeSelector } from "./engine/timeRangeControls.js";
import { getPanel } from "./panels/registry.js";
import "./panels/line.js";

const REFRESH_INTERVAL_MS = 60_000; // periodically re-fetch every panel so all data stays current

const params = new URLSearchParams(window.location.search);
const dashboardName = params.get("dashboard") || "rates";

const titleEl = document.querySelector("#app-title");
const lastUpdatedEl = document.querySelector("#last-updated");
const controlsEl = document.querySelector("#controls");
const gridEl = document.querySelector("#grid");

function formatTimestamp(date, periodAnchored) {
  if (periodAnchored) {
    // Period-anchored series (FRED daily/weekly/monthly values, stock daily bars)
    // label a whole day/week/month rather than a precise moment, always at a fixed
    // UTC time-of-day. Converting that to the viewer's local timezone can roll the
    // displayed calendar date back a day (e.g. UTC midnight becomes "yesterday,
    // 5 PM" in US timezones) - so these show their UTC calendar date instead.
    return date.toLocaleString(undefined, { dateStyle: "medium", timeZone: "UTC" });
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * A series is "period-anchored" if consecutive points repeat the same UTC
 * time-of-day, as opposed to genuinely intraday data (e.g. crypto ticks) whose
 * time-of-day varies point to point. See formatTimestamp for why this matters.
 */
function isPeriodAnchored(points) {
  if (points.length < 2) return false;
  const timeOfDay = (p) => p.timestamp.slice(11, 19); // "HH:MM:SS" portion of the ISO string
  return timeOfDay(points.at(-1)) === timeOfDay(points.at(-2));
}

const KNOWN_SERIES_LABELS = new Map(KNOWN_SERIES.map((s) => [s.id, s.label]));

/** Friendly legend name for a series expression, falling back to the raw expression. */
function traceLabel(expr) {
  return KNOWN_SERIES_LABELS.get(expr) || expr;
}

const GRID_MARGIN = 8;
const ROWS_VISIBLE = 2;
const SIZE_BOOST = 1.05; // tested as comfortably fitting with a bit of room to spare

/**
 * Sizes grid rows so that ROWS_VISIBLE rows of panels fill the browser's actual
 * visible height (accounting for the header and Chrome's own chrome/toolbars,
 * which shrink window.innerHeight rather than the page's CSS viewport).
 */
function computeCellHeight(panelHeightUnits) {
  const headerHeight = document.querySelector("header").offsetHeight;
  const gridPadding = 16; // #grid has 0.5rem padding on top and bottom
  const availableHeight = window.innerHeight - headerHeight - gridPadding;
  const totalUnits = panelHeightUnits * ROWS_VISIBLE;
  const totalMargins = GRID_MARGIN * (ROWS_VISIBLE + 1);
  return Math.max(
    40,
    Math.floor(((availableHeight - totalMargins) / totalUnits) * SIZE_BOOST),
  );
}

async function main() {
  const { spec, variables } = await loadDashboard(dashboardName);
  titleEl.textContent = spec.title;

  const panelHeightUnits = Math.max(4, ...spec.panels.map((p) => p.h || 4));
  const grid = GridStack.init(
    {
      column: 12,
      cellHeight: computeCellHeight(panelHeightUnits),
      margin: GRID_MARGIN,
    },
    gridEl,
  );
  window.addEventListener("resize", () => {
    grid.cellHeight(computeCellHeight(panelHeightUnits));
  });
  const instances = new Map();
  const renderTokens = new Map();
  const panelLatestTimestamps = new Map();
  let timeRangeSelector;

  for (const panelSpec of spec.panels) {
    addPanelWidget(grid, panelSpec);
  }

  function updateLastUpdatedDisplay() {
    let latest = null;
    for (const entry of panelLatestTimestamps.values()) {
      if (!latest || entry.date > latest.date) latest = entry;
    }
    lastUpdatedEl.textContent = latest
      ? `as of ${formatTimestamp(latest.date, latest.periodAnchored)}`
      : "";
  }

  function destroyPanel(panelId) {
    instances.get(panelId)?.destroy();
    instances.delete(panelId);
  }

  async function renderPanel(panelSpec) {
    // Guards against out-of-order async responses: if range/series change again
    // before this call's fetch resolves, a newer renderPanel call for the same
    // panel bumps the token, and this stale call becomes a no-op instead of
    // overwriting the newer render with older data.
    const token = (renderTokens.get(panelSpec.id) ?? 0) + 1;
    renderTokens.set(panelSpec.id, token);

    const seriesList = Array.isArray(panelSpec.series)
      ? panelSpec.series
      : [panelSpec.series];
    const range = panelSpec.timeRange || timeRangeSelector.value;
    const resolvedExprs = seriesList.map((s) =>
      substituteVariables(s, variables),
    );

    const results = await Promise.all(
      resolvedExprs.map((expr) =>
        fetchSeries(expr, range, panelSpec.transform || "none"),
      ),
    );
    if (renderTokens.get(panelSpec.id) !== token) return;

    const traces = results.map((result, i) => ({
      label: traceLabel(resolvedExprs[i]),
      points: result.points,
    }));

    const latestByTrace = traces
      .map((t) => {
        const last = t.points.at(-1);
        return last && { timestamp: last.timestamp, periodAnchored: isPeriodAnchored(t.points) };
      })
      .filter(Boolean)
      .reduce(
        (latest, c) => (!latest || c.timestamp > latest.timestamp ? c : latest),
        null,
      );
    if (latestByTrace) {
      panelLatestTimestamps.set(panelSpec.id, {
        date: new Date(latestByTrace.timestamp),
        periodAnchored: latestByTrace.periodAnchored,
      });
    } else {
      panelLatestTimestamps.delete(panelSpec.id);
    }
    updateLastUpdatedDisplay();

    destroyPanel(panelSpec.id);

    const el = document.getElementById(`panel-${panelSpec.id}`);
    const panelModule = getPanel(panelSpec.type);
    const instance = panelModule.render(
      el,
      { traces },
      {
        title: panelSpec.title,
        color: panelSpec.color,
        referenceLine: panelSpec.referenceLine,
      },
    );
    instances.set(panelSpec.id, instance);
  }

  async function renderAll() {
    await Promise.all(
      spec.panels.map((panelSpec) =>
        panelSpec.series
          ? renderPanel(panelSpec).catch((err) =>
              showPanelError(panelSpec.id, err),
            )
          : undefined,
      ),
    );
  }

  // The dashboard JSON's `timeRange` is only a fallback default (and gets overwritten
  // whenever edit mode's Save button runs, capturing whatever's active at that moment).
  // The range you actually pick while browsing is remembered per-dashboard in
  // localStorage instead, so it survives reloads independent of that save behavior.
  const timeRangeStorageKey = `financial-dashboard:timeRange:${dashboardName}`;
  const storedTimeRange = localStorage.getItem(timeRangeStorageKey);

  timeRangeSelector = createTimeRangeSelector(
    controlsEl,
    storedTimeRange || spec.timeRange || "1Y",
    (range) => {
      localStorage.setItem(timeRangeStorageKey, range);
      renderAll().catch(reportError);
    },
  );

  createEditMode({
    grid,
    spec,
    dashboardName,
    controlsEl,
    gridEl,
    renderPanel,
    destroyPanel,
  });

  await renderAll();
  setInterval(() => {
    renderAll().catch(reportError);
  }, REFRESH_INTERVAL_MS);
}

function reportError(err) {
  console.error(err);
  titleEl.textContent = `Error: ${err.message}`;
}

function showPanelError(panelId, err) {
  console.error(err);
  const el = document.getElementById(`panel-${panelId}`);
  if (el) el.textContent = `Error: ${err.message}`;
}

main().catch(reportError);
