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
export const getAdminDashboardCopy = dashboardCopy.get

export const registerAdminDashboardConfig = dashboardConfig.register
export const getAdminDashboardConfig = dashboardConfig.get

export const registerAdminDashboardActionMeta = dashboardActionMeta.register
export const getAdminDashboardActionMeta = dashboardActionMeta.get

export const registerAdminDashboardAction = dashboardActions.register
export function getAdminDashboardAction(context = {}, key = '') {
  return dashboardActions.getByKey(context, key)
}
