import Plotly from "plotly.js-dist-min";
import { COLOR_PALETTE, DEFAULT_COLOR } from "../engine/colorPalette.js";
import { registerPanel } from "./registry.js";

function toXY(points) {
  return { x: points.map((p) => p.timestamp), y: points.map((p) => p.value) };
}

/** Builds one Plotly trace per series; auto-assigns palette colors when overlaying more than one. */
function buildTraces(traces, singleColor) {
  return traces.map((trace, i) => {
    const { x, y } = toXY(trace.points);
    const color =
      traces.length === 1
        ? singleColor || DEFAULT_COLOR
        : COLOR_PALETTE[i % COLOR_PALETTE.length].value;
    return {
      x,
      y,
      type: "scatter",
      mode: "lines",
      name: trace.label,
      line: { color },
    };
  });
}

/** A horizontal dotted line + value label at a fixed y-value (e.g. purchase price, decision threshold). */
function buildReferenceLine(referenceLine) {
  if (typeof referenceLine !== "number" || !Number.isFinite(referenceLine)) {
    return { shapes: [], annotations: [] };
  }
  return {
    shapes: [
      {
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        yref: "y",
        y0: referenceLine,
        y1: referenceLine,
        line: { color: "#8b96a5", width: 1, dash: "dot" },
      },
    ],
    annotations: [
      {
        xref: "paper",
        x: 1,
        xanchor: "right",
        yref: "y",
        y: referenceLine,
        yanchor: "bottom",
        text: String(referenceLine),
        showarrow: false,
        font: { size: 10, color: "#8b96a5" },
      },
    ],
  };
}

/** Line panel: renders one or more overlaid Plotly line traces. Returns { update(points), destroy() }. */
function render(el, data, options = {}) {
  const traces = buildTraces(data.traces, options.color);
  const titleText = options.title;
  const { shapes, annotations } = buildReferenceLine(options.referenceLine);
  Plotly.newPlot(
    el,
    traces,
    {
      title: titleText ? { text: titleText } : undefined,
      showlegend: data.traces.length > 1,
      legend: { orientation: "h", y: -0.2, font: { size: 9, color: "#6b7280" } },
      shapes,
      annotations,
      margin: {
        t: options.title ? 32 : 8,
        r: 8,
        b: data.traces.length > 1 ? 40 : 32,
        l: 48,
      },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#cfd3da" },
      xaxis: { gridcolor: "#2a2f37" },
      yaxis: { gridcolor: "#2a2f37" },
    },
    { responsive: true, displayModeBar: false },
  );

  // GridStack can finalize an item's true pixel size slightly after mount, and
  // Plotly's own `responsive: true` sometimes misses that first resize, leaving
  // the chart stuck smaller than its container. Watch the container directly.
  const resizeObserver = new ResizeObserver(() => {
    Plotly.Plots.resize(el);
  });
  resizeObserver.observe(el);

  return {
    update(points) {
      // Only used for live updates, which only apply to single-series panels (trace 0).
      const { x, y } = toXY(points);
      Plotly.update(el, { x: [x], y: [y] }, {}, [0]);
    },
    destroy() {
      resizeObserver.disconnect();
      Plotly.purge(el);
    },
  };
}

registerPanel("line", { render });
