export const TIME_RANGES = ["1D", "1W", "1M", "YTD", "1Y", "5Y", "Max"];

/**
 * Renders a global time-range selector into `container` and calls `onChange(range)`
 * whenever the user picks a different range. Returns the currently selected range via `.value`.
 */
export function createTimeRangeSelector(container, defaultRange, onChange) {
  let current = TIME_RANGES.includes(defaultRange) ? defaultRange : "1Y";

  const wrapper = document.createElement("div");
  wrapper.className = "time-range-selector";

  const buttons = TIME_RANGES.map((range) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = range;
    button.className = range === current ? "active" : "";
    button.addEventListener("click", () => {
      if (range === current) return;
      current = range;
      for (const b of buttons)
        b.classList.toggle("active", b.textContent === current);
      onChange(current);
    });
    wrapper.appendChild(button);
    return button;
  });

  container.appendChild(wrapper);

  return {
    get value() {
      return current;
    },
  };
}
