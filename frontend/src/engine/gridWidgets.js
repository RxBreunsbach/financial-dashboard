/** Adds a GridStack widget for a panel and returns the empty .panel div to render into.
 *
 * GridStack v10+ defaults to treating `content` as plain text (XSS-safe by
 * default), so widget bodies must be built with DOM APIs instead of HTML strings.
 */
export function addPanelWidget(grid, panelSpec) {
  const widgetEl = grid.addWidget({
    id: panelSpec.id,
    x: panelSpec.x,
    y: panelSpec.y,
    w: panelSpec.w,
    h: panelSpec.h,
  });
  const panelDiv = document.createElement("div");
  panelDiv.className = "panel";
  panelDiv.id = `panel-${panelSpec.id}`;
  widgetEl.querySelector(".grid-stack-item-content").appendChild(panelDiv);
  return panelDiv;
}
