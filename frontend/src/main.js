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
import {
  createTimeRangeSelector,
  TIME_RANGES,
} from "./engine/timeRangeControls.js";
import { WebSocketClient } from "./engine/websocketClient.js";
import { getPanel } from "./panels/registry.js";
import "./panels/line.js";

const SINGLE_SERIES_ID = /^[a-zA-Z][a-zA-Z0-9_]*:[a-zA-Z0-9_.-]+$/;

const params = new URLSearchParams(window.location.search);
const dashboardName = params.get("dashboard") || "rates";

const titleEl = document.querySelector("#app-title");
const controlsEl = document.querySelector("#controls");
const gridEl = document.querySelector("#grid");
const wsClient = new WebSocketClient();

/** Keyword ranges (1D/1W/.../Max) always resolve to "now" as their end; explicit "start:end" ranges don't. */
function rangeIncludesNow(range) {
  return TIME_RANGES.includes(range) || range.toUpperCase() === "YTD";
}

async function main() {
  const { spec, variables } = await loadDashboard(dashboardName);
  titleEl.textContent = spec.title;

  const grid = GridStack.init(
    { column: 12, cellHeight: 80, margin: 8 },
    gridEl,
  );
  const instances = new Map();
  const liveUnsubscribers = new Map();
  const renderTokens = new Map();
  let timeRangeSelector;

  for (const panelSpec of spec.panels) {
    addPanelWidget(grid, panelSpec);
  }

  function destroyPanel(panelId) {
    liveUnsubscribers.get(panelId)?.();
    liveUnsubscribers.delete(panelId);
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
      label: resolvedExprs[i],
      points: result.points,
    }));

    destroyPanel(panelSpec.id);

    const el = document.getElementById(`panel-${panelSpec.id}`);
    const panelModule = getPanel(panelSpec.type);
    const instance = panelModule.render(
      el,
      { traces },
      {
        title: panelSpec.title,
        color: panelSpec.color,
        live: Boolean(panelSpec.live),
        referenceLine: panelSpec.referenceLine,
      },
    );
    instances.set(panelSpec.id, instance);

    // Live streaming only makes sense for a single raw series id, not a multi-series overlay.
    if (
      panelSpec.live &&
      resolvedExprs.length === 1 &&
      rangeIncludesNow(range) &&
      SINGLE_SERIES_ID.test(resolvedExprs[0])
    ) {
      const points = [...traces[0].points];
      const unsubscribe = await wsClient.subscribe(
        resolvedExprs[0],
        (point) => {
          if (renderTokens.get(panelSpec.id) !== token) return;
          points.push({ timestamp: point.timestamp, value: point.value });
          instance.update(points);
        },
      );
      if (renderTokens.get(panelSpec.id) !== token) {
        // A newer render started while we were subscribing; abandon this one.
        unsubscribe();
        return;
      }
      liveUnsubscribers.set(panelSpec.id, unsubscribe);
    }
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

  timeRangeSelector = createTimeRangeSelector(
    controlsEl,
    spec.timeRange || "1Y",
    () => {
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
