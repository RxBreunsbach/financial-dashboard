const API_BASE_URL = "http://localhost:8000";

/**
 * Fetch a single series (or expression) from the backend /query endpoint.
 * Returns { series, range, transform, points: [{ timestamp, value }] }.
 */
export async function fetchSeries(series, range, transform = "none") {
  const url = new URL("/query", API_BASE_URL);
  url.searchParams.set("series", series);
  url.searchParams.set("range", range);
  url.searchParams.set("transform", transform);

  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail || `Query failed with status ${response.status}`,
    );
  }
  return response.json();
}

export async function fetchDashboard(name) {
  const response = await fetch(new URL(`/dashboards/${name}`, API_BASE_URL));
  if (!response.ok) {
    throw new Error(
      `Could not load dashboard "${name}" (status ${response.status})`,
    );
  }
  return response.json();
}

export async function saveDashboard(name, spec) {
  const response = await fetch(new URL(`/dashboards/${name}`, API_BASE_URL), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail ||
        `Could not save dashboard "${name}" (status ${response.status})`,
    );
  }
  return response.json();
}
