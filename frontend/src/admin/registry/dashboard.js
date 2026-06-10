import { createListItemRegistry, createSingleItemRegistry } from './shared.js'


const dashboardStats = createListItemRegistry({ iconClass: '' })
const dashboardStatusSummaries = createListItemRegistry()
const dashboardStatusBadges = createListItemRegistry({ tone: 'neutral' })
const dashboardStatusItems = createListItemRegistry()
const dashboardAlerts = createListItemRegistry({ tone: 'warning' })
const dashboardQueueMetrics = createListItemRegistry({ variant: 'stat' })
const dashboardCopy = createSingleItemRegistry()
const dashboardConfig = createSingleItemRegistry()
const dashboardActionMeta = createSingleItemRegistry()
const dashboardActions = createListItemRegistry()

export const registerAdminDashboardStat = dashboardStats.register
export const getAdminDashboardStats = dashboardStats.get

export const registerAdminDashboardStatusSummary = dashboardStatusSummaries.register
export const getAdminDashboardStatusSummaries = dashboardStatusSummaries.get

export const registerAdminDashboardStatusBadge = dashboardStatusBadges.register
export const getAdminDashboardStatusBadges = dashboardStatusBadges.get

export const registerAdminDashboardStatusItem = dashboardStatusItems.register
export const getAdminDashboardStatusItems = dashboardStatusItems.get

export const registerAdminDashboardAlert = dashboardAlerts.register
export const getAdminDashboardAlerts = dashboardAlerts.get

export const registerAdminDashboardQueueMetric = dashboardQueueMetrics.register
export const getAdminDashboardQueueMetrics = dashboardQueueMetrics.get

export const registerAdminDashboardCopy = dashboardCopy.register
export const getAdminDashboardCopy = context => mergeDashboardContributions(dashboardCopy.getAll(context))

export const registerAdminDashboardConfig = dashboardConfig.register
export const getAdminDashboardConfig = context => mergeDashboardContributions(dashboardConfig.getAll(context), { deep: true })

export const registerAdminDashboardActionMeta = dashboardActionMeta.register
export const getAdminDashboardActionMeta = context => mergeDashboardContributions(dashboardActionMeta.getAll(context))

export const registerAdminDashboardAction = dashboardActions.register
export function getAdminDashboardAction(context = {}, key = '') {
  return dashboardActions.getByKey(context, key)
}

function mergeDashboardContributions(items, { deep = false } = {}) {
  if (!Array.isArray(items) || !items.length) {
    return null
  }

  return [...items].reverse().reduce((merged, item) => (
    deep ? deepMerge(merged, item) : shallowMerge(merged, item)
  ), {})
}

function shallowMerge(target, source) {
  const merged = { ...target }
  for (const [key, value] of Object.entries(source || {})) {
    merged[key] = value
  }
  return merged
}

function deepMerge(target, source) {
  if (!isPlainObject(target)) {
    return cloneMergeValue(source)
  }
  if (!isPlainObject(source)) {
    return cloneMergeValue(source)
  }

  const merged = { ...target }
  for (const [key, value] of Object.entries(source)) {
    if (isPlainObject(value) && isPlainObject(merged[key])) {
      merged[key] = deepMerge(merged[key], value)
    } else if (Array.isArray(value) && Array.isArray(merged[key])) {
      merged[key] = [...merged[key], ...value]
    } else {
      merged[key] = cloneMergeValue(value)
    }
  }
  return merged
}

function cloneMergeValue(value) {
  if (Array.isArray(value)) {
    return [...value]
  }
  if (isPlainObject(value)) {
    return deepMerge({}, value)
  }
  return value
}

function isPlainObject(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}
