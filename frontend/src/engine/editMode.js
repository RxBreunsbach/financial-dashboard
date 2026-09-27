import { saveDashboard } from "./apiClient.js";
import { COLOR_PALETTE } from "./colorPalette.js";
import { addPanelWidget } from "./gridWidgets.js";
import { KNOWN_SERIES } from "./knownSeries.js";

let newPanelCounter = 0;

/** panelSpec.series is a string (single expression) or an array (multi-series overlay). */
function hasValidSeries(series) {
  if (Array.isArray(series))
    return series.length > 0 && series.every((s) => s.includes(":"));
  return typeof series === "string" && series.includes(":");
}

function seriesToInputValue(series) {
  return Array.isArray(series) ? series.join(", ") : (series ?? "");
}

/** Splits on top-level commas: one part stays a single expression, 2+ parts become an overlay array. */
function parseSeriesInput(value) {
  const parts = value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.length > 1 ? parts : value;
}

/**
 * Adds an Edit-mode toggle to the dashboard: enables GridStack drag/resize,
 * a click-to-select panel editor (title/series/transform/timeRange/live),
 * add/remove panel buttons, and a Save button that PUTs the spec back to
 * the backend (which writes it to dashboards/<name>.json).
 */
export function createEditMode({
  grid,
  spec,
  dashboardName,
  controlsEl,
  gridEl,
  renderPanel,
  destroyPanel,
}) {
  let editing = false;
  let selectedId = null;

  const toggleButton = document.createElement("button");
  toggleButton.type = "button";
  toggleButton.textContent = "Edit";
  toggleButton.className = "edit-toggle";
  controlsEl.appendChild(toggleButton);

  const toolbar = document.createElement("div");
  toolbar.className = "edit-toolbar hidden";
  toolbar.innerHTML = `
    <button type="button" data-action="add">+ Add panel</button>
    <button type="button" data-action="remove" disabled>Remove selected</button>
    <button type="button" data-action="save">Save</button>
    <span class="edit-status"></span>
  `;
  controlsEl.insertAdjacentElement("afterend", toolbar);

  const editorForm = document.createElement("form");
  editorForm.className = "panel-editor hidden";
  editorForm.innerHTML = `
    <label>Title <input name="title" /></label>
    <div class="series-field">
      <label>Series <input name="series" list="known-series" placeholder="fred:DGS10 - fred:DGS2" /></label>
      <datalist id="known-series">
        ${KNOWN_SERIES.map((s) => `<option value="${s.id}">${s.label}</option>`).join("")}
      </datalist>
      <details class="series-picker">
        <summary>Choose from list ▾</summary>
        <div class="series-picker-menu">
          ${KNOWN_SERIES.map(
            (s) =>
              `<label class="series-picker-item"><input type="checkbox" value="${s.id}" /> ${s.label}</label>`,
          ).join("")}
        </div>
      </details>
    </div>
    <label>Transform <input name="transform" placeholder="none" /></label>
    <label>Time range <input name="timeRange" placeholder="(uses global range)" /></label>
    <label>Reference line <input name="referenceLine" type="number" step="any" placeholder="e.g. purchase price" /></label>
    <label class="checkbox"><input type="checkbox" name="live" /> Live</label>
    <div class="color-swatches" role="group" aria-label="Line color">
      ${COLOR_PALETTE.map(
        (c) =>
          `<button type="button" class="color-swatch" data-color="${c.value}" style="background:${c.value}" title="${c.label}" aria-label="${c.label}"></button>`,
      ).join("")}
    </div>
  `;
  toolbar.insertAdjacentElement("afterend", editorForm);

  const statusEl = toolbar.querySelector(".edit-status");
  const removeButton = toolbar.querySelector('[data-action="remove"]');
  const colorSwatches = [...editorForm.querySelectorAll(".color-swatch")];
  const seriesPicker = editorForm.querySelector(".series-picker");
  const seriesCheckboxes = [
    ...editorForm.querySelectorAll(
      '.series-picker-item input[type="checkbox"]',
    ),
  ];

  function findPanel(id) {
    return spec.panels.find((p) => p.id === id);
  }

  function setSelected(id) {
    selectedId = id;
    for (const el of gridEl.querySelectorAll(".grid-stack-item")) {
      el.classList.toggle("selected", el.getAttribute("gs-id") === id);
    }
    removeButton.disabled = !id;

    const panelSpec = id ? findPanel(id) : null;
    editorForm.classList.toggle("hidden", !panelSpec);
    if (panelSpec) {
      editorForm.elements.title.value = panelSpec.title ?? "";
      editorForm.elements.series.value = seriesToInputValue(panelSpec.series);
      editorForm.elements.transform.value = panelSpec.transform ?? "";
      editorForm.elements.timeRange.value = panelSpec.timeRange ?? "";
      editorForm.elements.referenceLine.value =
        panelSpec.referenceLine ?? "";
      editorForm.elements.live.checked = Boolean(panelSpec.live);
      const activeColor = panelSpec.color || COLOR_PALETTE[0].value;
      for (const swatch of colorSwatches) {
        swatch.classList.toggle(
          "selected",
          swatch.dataset.color === activeColor,
        );
      }

      const currentIds = Array.isArray(panelSpec.series)
        ? panelSpec.series
        : [panelSpec.series];
      for (const cb of seriesCheckboxes) {
        cb.checked = currentIds.includes(cb.value);
      }
    }
  }

  seriesPicker.addEventListener("change", (event) => {
    if (event.target.type !== "checkbox") return;
    const ids = seriesCheckboxes
      .filter((cb) => cb.checked)
      .map((cb) => cb.value);
    editorForm.elements.series.value = ids.join(", ");
    editorForm.elements.series.dispatchEvent(
      new Event("input", { bubbles: true }),
    );
  });

  // Close the dropdown when clicking anywhere outside it.
  document.addEventListener("click", (event) => {
    if (seriesPicker.open && !seriesPicker.contains(event.target)) {
      seriesPicker.open = false;
    }
  });

  editorForm.addEventListener("click", (event) => {
    const swatch = event.target.closest(".color-swatch");
    if (!swatch) return;
    const panelSpec = findPanel(selectedId);
    if (!panelSpec) return;

    panelSpec.color = swatch.dataset.color;
    for (const s of colorSwatches) {
      s.classList.toggle("selected", s === swatch);
    }
    if (hasValidSeries(panelSpec.series)) {
      renderPanel(panelSpec).catch((err) => {
        statusEl.textContent = `Error: ${err.message}`;
      });
    }
  });

  editorForm.addEventListener("input", () => {
    const panelSpec = findPanel(selectedId);
    if (!panelSpec) return;
    panelSpec.title = editorForm.elements.title.value || undefined;
    panelSpec.series = parseSeriesInput(editorForm.elements.series.value);
    panelSpec.transform = editorForm.elements.transform.value || undefined;
    panelSpec.timeRange = editorForm.elements.timeRange.value || undefined;
    panelSpec.referenceLine = editorForm.elements.referenceLine.value
      ? Number(editorForm.elements.referenceLine.value)
      : undefined;
    panelSpec.live = editorForm.elements.live.checked;

    if (hasValidSeries(panelSpec.series)) {
      renderPanel(panelSpec).catch((err) => {
        statusEl.textContent = `Error: ${err.message}`;
      });
    }
  });

  gridEl.addEventListener("click", (event) => {
    if (!editing) return;
    const item = event.target.closest(".grid-stack-item");
    setSelected(item ? item.getAttribute("gs-id") : null);
  });

  toolbar.addEventListener("click", (event) => {
    const action = event.target.dataset.action;
    if (action === "add") {
      addPanel();
    } else if (action === "remove" && selectedId) {
      removePanel(selectedId);
    } else if (action === "save") {
      save();
    }
  });

  function addPanel() {
    const id = `new-${Date.now()}-${newPanelCounter++}`;
    const panelSpec = {
      id,
      type: "line",
      x: 0,
      y: 0,
      w: 4,
      h: 4,
      series: "",
      title: "New panel",
    };
    spec.panels.push(panelSpec);
    addPanelWidget(grid, panelSpec);
    setSelected(id);
  }

  function removePanel(id) {
    destroyPanel(id);
    const el = gridEl.querySelector(`.grid-stack-item[gs-id="${id}"]`);
    if (el) grid.removeWidget(el);
    spec.panels = spec.panels.filter((p) => p.id !== id);
    setSelected(null);
  }

  function applyLayoutFromGrid() {
    for (const node of grid.save(false)) {
      const panelSpec = findPanel(node.id);
      if (panelSpec)
        Object.assign(panelSpec, {
          x: node.x,
          y: node.y,
          w: node.w,
          h: node.h,
        });
    }
  }

  async function save() {
    applyLayoutFromGrid();
    statusEl.textContent = "Saving\u2026";
    try {
      await saveDashboard(dashboardName, spec);
      statusEl.textContent = "Saved";
    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`;
    }
  }

  toggleButton.addEventListener("click", () => {
    editing = !editing;
    grid.setStatic(!editing);
    toggleButton.textContent = editing ? "Done" : "Edit";
    toolbar.classList.toggle("hidden", !editing);
    if (!editing) setSelected(null);
  });
}
