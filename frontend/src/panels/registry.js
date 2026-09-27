const registry = new Map();

/** Registers a panel type. `module` must expose render(el, data, options) -> { update, destroy }. */
export function registerPanel(type, module) {
  registry.set(type, module);
}

export function getPanel(type) {
  const module = registry.get(type);
  if (!module) {
    throw new Error(`No panel registered for type "${type}"`);
  }
  return module;
}
