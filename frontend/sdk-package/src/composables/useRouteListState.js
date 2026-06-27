import { computed } from 'vue'

function getDefaultOmitWhen(defaultValue) {
  return value => value === defaultValue || value === undefined || value === null || value === ''
}

export function useRouteListState({
  route,
  router,
  resolveTarget,
  schema
}) {
  const entries = Object.entries(schema).map(([stateKey, config]) => ({
    stateKey,
    queryKey: config.queryKey || stateKey,
    defaultValue: config.defaultValue,
    normalize: config.normalize || (value => value),
    serialize: config.serialize || (value => String(value)),
    omitWhen: config.omitWhen || getDefaultOmitWhen(config.defaultValue),
  }))

  function resolveState(overrides = {}) {
    return entries.reduce((state, entry) => {
      const hasOverride = Object.prototype.hasOwnProperty.call(overrides, entry.stateKey)
      const rawValue = hasOverride ? overrides[entry.stateKey] : route.query[entry.queryKey]
      const normalizedValue = entry.normalize(rawValue, state)
      state[entry.stateKey] = normalizedValue ?? entry.defaultValue
      return state
    }, {})
  }

  const state = Object.fromEntries(
    entries.map(entry => [
      entry.stateKey,
      computed(() => resolveState()[entry.stateKey]),
    ])
  )

  function buildQuery(overrides = {}) {
    const resolvedState = resolveState(overrides)

    return entries.reduce((query, entry) => {
      const value = resolvedState[entry.stateKey]
      if (entry.omitWhen(value, resolvedState)) {
        return query
      }

      query[entry.queryKey] = entry.serialize(value, resolvedState)
      return query
    }, {})
  }

  async function navigate(overrides = {}, { replace = false } = {}) {
    const target = typeof resolveTarget === 'function' ? resolveTarget(route) : (resolveTarget || {})
    const location = {
      ...target,
      query: buildQuery(overrides),
    }

    if (replace) {
      return router.replace(location)
    }

    return router.push(location)
  }

  return {
    ...state,
    buildQuery,
    replace: overrides => navigate(overrides, { replace: true }),
    push: overrides => navigate(overrides),
    snapshot: resolveState,
  }
}
