import { fetchDashboard } from "./apiClient.js";

/** Loads a dashboard spec and resolves its variables against defaults/overrides. */
export async function loadDashboard(name, overrides = {}) {
  const spec = await fetchDashboard(name);
  const variables = {};
  for (const variable of spec.variables ?? []) {
    variables[variable.name] = overrides[variable.name] ?? variable.default;
  }
  return { spec, variables };
}

/** Replaces $name tokens (e.g. "stock:$symbol") with resolved variable values. */
export function substituteVariables(text, variables) {
  return text.replace(/\$(\w+)/g, (match, name) => (name in variables ? variables[name] : match));
}
