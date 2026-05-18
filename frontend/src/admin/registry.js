import DashboardPage from './views/DashboardPage.vue'
import ModulesPage from './views/ModulesPage.vue'
import BasicsPage from './views/BasicsPage.vue'
import PermissionsPage from './views/PermissionsPage.vue'
import UsersPage from './views/UsersPage.vue'
import FlagsPage from './views/FlagsPage.vue'
import ApprovalQueuePage from './views/ApprovalQueuePage.vue'
import AuditLogsPage from './views/AuditLogsPage.vue'
import AppearancePage from './views/AppearancePage.vue'
import TagsPage from './views/TagsPage.vue'
import MailPage from './views/MailPage.vue'
import AdvancedPage from './views/AdvancedPage.vue'

const adminRoutes = []
const adminDashboardStats = []
const adminDashboardStatusSummaries = []
const adminDashboardStatusBadges = []
const adminDashboardStatusItems = []
const adminDashboardAlerts = []
const adminDashboardQueueMetrics = []
const adminDashboardCopies = []
const adminDashboardConfig = []
const adminDashboardActionsMeta = []
const adminDashboardActions = []
const adminModulesPageCopies = []
const adminModulesPageConfig = []
const adminModulesPageActionMeta = []
const adminBasicsPageCopies = []
const adminBasicsPageConfig = []
const adminBasicsPageActionMeta = []
const adminAppearancePageCopies = []
const adminAppearancePageConfig = []
const adminAppearancePageActionMeta = []
const adminMailPageCopies = []
const adminMailPageConfig = []
const adminMailPageActionMeta = []
const adminAdvancedPageCopies = []
const adminAdvancedPageConfig = []
const adminAdvancedPageActionMeta = []
const adminAuditLogsPageCopies = []
const adminAuditLogsPageConfig = []
const adminApprovalQueuePageCopies = []
const adminApprovalQueuePageConfig = []
const adminApprovalQueuePageActionMeta = []
const adminApprovalQueueNoteTemplates = []
const adminFlagsPageCopies = []
const adminFlagsPageConfig = []
const adminFlagsPageActionMeta = []
const adminPermissionsPageCopies = []
const adminPermissionsPageConfig = []
const adminPermissionsPageActionMeta = []
const adminUsersPageCopies = []
const adminUsersPageConfig = []
const adminUsersPageActionMeta = []
const adminTagsPageConfig = []
const adminTagsPageCopies = []
const adminTagsPageActionMeta = []

function upsertByPath(target, value) {
  const existingIndex = target.findIndex(item => item.path === value.path)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function upsertByKey(target, value) {
  const existingIndex = target.findIndex(item => item.key === value.key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function resolveAdminItem(item, context = {}) {
  const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
  if (!isVisible) {
    return null
  }

  const resolvedItem = typeof item.resolve === 'function'
    ? item.resolve(context)
    : item

  if (!resolvedItem) {
    return null
  }

  return {
    ...item,
    ...resolvedItem,
  }
}

export function registerAdminRoute(route) {
  const normalizedRoute = {
    navSection: 'feature',
    navOrder: 100,
    showInNavigation: true,
    showInDashboardActions: false,
    dashboardActionOrder: null,
    dashboardActionLabel: '',
    navDescription: '',
    navBadge: '',
    ...route
  }

  return upsertByPath(adminRoutes, normalizedRoute)
}

export function getAdminRoutes() {
  return [...adminRoutes].sort((left, right) => {
    if (left.path === '/admin') return -1
    if (right.path === '/admin') return 1
    return (left.navOrder || 100) - (right.navOrder || 100)
  })
}

export function getAdminNavSections() {
  const sections = {
    core: { key: 'core', title: '核心', items: [] },
    feature: { key: 'feature', title: '功能', items: [] }
  }

  for (const route of getAdminRoutes()) {
    if (!route.showInNavigation) {
      continue
    }

    const section = sections[route.navSection] || sections.feature
    section.items.push({
      path: route.path,
      icon: route.icon,
      label: route.label,
      description: route.navDescription || '',
      badge: route.navBadge || '',
      moduleId: route.moduleId || 'core',
      navOrder: route.navOrder || 100
    })
  }

  return Object.values(sections)
    .map(section => ({
      ...section,
      items: section.items.sort((left, right) => left.navOrder - right.navOrder)
    }))
    .filter(section => section.items.length > 0)
}

export function getAdminDashboardActions() {
  return getAdminRoutes()
    .filter(route => route.showInDashboardActions)
    .sort((left, right) => {
      const leftOrder = left.dashboardActionOrder ?? left.navOrder ?? 100
      const rightOrder = right.dashboardActionOrder ?? right.navOrder ?? 100
      return leftOrder - rightOrder
    })
    .map(route => ({
      key: route.name || route.path,
      to: route.path,
      icon: route.icon,
      label: route.dashboardActionLabel || route.label,
      description: route.navDescription || '',
      moduleId: route.moduleId || 'core',
    }))
}

export function registerAdminDashboardStat(item) {
  const normalizedItem = {
    order: 100,
    iconClass: '',
    ...item,
  }

  return upsertByKey(adminDashboardStats, normalizedItem)
}

export function getAdminDashboardStats(context = {}) {
  return [...adminDashboardStats]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardStatusSummary(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardStatusSummaries, normalizedItem)
}

export function getAdminDashboardStatusSummaries(context = {}) {
  return [...adminDashboardStatusSummaries]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardStatusBadge(item) {
  const normalizedItem = {
    order: 100,
    tone: 'neutral',
    ...item,
  }

  return upsertByKey(adminDashboardStatusBadges, normalizedItem)
}

export function getAdminDashboardStatusBadges(context = {}) {
  return [...adminDashboardStatusBadges]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardStatusItem(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardStatusItems, normalizedItem)
}

export function getAdminDashboardStatusItems(context = {}) {
  return [...adminDashboardStatusItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardAlert(item) {
  const normalizedItem = {
    order: 100,
    tone: 'warning',
    ...item,
  }

  return upsertByKey(adminDashboardAlerts, normalizedItem)
}

export function getAdminDashboardAlerts(context = {}) {
  return [...adminDashboardAlerts]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardQueueMetric(item) {
  const normalizedItem = {
    order: 100,
    variant: 'stat',
    ...item,
  }

  return upsertByKey(adminDashboardQueueMetrics, normalizedItem)
}

export function getAdminDashboardQueueMetrics(context = {}) {
  return [...adminDashboardQueueMetrics]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminDashboardCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardCopies, normalizedItem)
}

export function getAdminDashboardCopy(context = {}) {
  return [...adminDashboardCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminDashboardConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardConfig, normalizedItem)
}

export function getAdminDashboardConfig(context = {}) {
  return [...adminDashboardConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminDashboardActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardActionsMeta, normalizedItem)
}

export function getAdminDashboardActionMeta(context = {}) {
  return [...adminDashboardActionsMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminDashboardAction(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminDashboardActions, normalizedItem)
}

export function getAdminDashboardAction(context = {}, key = '') {
  if (!key) return null

  return [...adminDashboardActions]
    .filter(item => item.key === key)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminModulesPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminModulesPageCopies, normalizedItem)
}

export function getAdminModulesPageCopy(context = {}) {
  return [...adminModulesPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminModulesPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminModulesPageConfig, normalizedItem)
}

export function getAdminModulesPageConfig(context = {}) {
  return [...adminModulesPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminModulesPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminModulesPageActionMeta, normalizedItem)
}

export function getAdminModulesPageActionMeta(context = {}) {
  return [...adminModulesPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminBasicsPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminBasicsPageCopies, normalizedItem)
}

export function getAdminBasicsPageCopy(context = {}) {
  return [...adminBasicsPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminBasicsPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminBasicsPageConfig, normalizedItem)
}

export function getAdminBasicsPageConfig(context = {}) {
  return [...adminBasicsPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminBasicsPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminBasicsPageActionMeta, normalizedItem)
}

export function getAdminBasicsPageActionMeta(context = {}) {
  return [...adminBasicsPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAppearancePageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAppearancePageCopies, normalizedItem)
}

export function getAdminAppearancePageCopy(context = {}) {
  return [...adminAppearancePageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAppearancePageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAppearancePageConfig, normalizedItem)
}

export function getAdminAppearancePageConfig(context = {}) {
  return [...adminAppearancePageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAppearancePageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAppearancePageActionMeta, normalizedItem)
}

export function getAdminAppearancePageActionMeta(context = {}) {
  return [...adminAppearancePageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminMailPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminMailPageCopies, normalizedItem)
}

export function getAdminMailPageCopy(context = {}) {
  return [...adminMailPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminMailPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminMailPageConfig, normalizedItem)
}

export function getAdminMailPageConfig(context = {}) {
  return [...adminMailPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminMailPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminMailPageActionMeta, normalizedItem)
}

export function getAdminMailPageActionMeta(context = {}) {
  return [...adminMailPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAdvancedPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAdvancedPageCopies, normalizedItem)
}

export function getAdminAdvancedPageCopy(context = {}) {
  return [...adminAdvancedPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAdvancedPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAdvancedPageConfig, normalizedItem)
}

export function getAdminAdvancedPageConfig(context = {}) {
  return [...adminAdvancedPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAdvancedPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAdvancedPageActionMeta, normalizedItem)
}

export function getAdminAdvancedPageActionMeta(context = {}) {
  return [...adminAdvancedPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAuditLogsPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAuditLogsPageCopies, normalizedItem)
}

export function getAdminAuditLogsPageCopy(context = {}) {
  return [...adminAuditLogsPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminAuditLogsPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminAuditLogsPageConfig, normalizedItem)
}

export function getAdminAuditLogsPageConfig(context = {}) {
  return [...adminAuditLogsPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminApprovalQueuePageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminApprovalQueuePageCopies, normalizedItem)
}

export function getAdminApprovalQueuePageCopy(context = {}) {
  return [...adminApprovalQueuePageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminApprovalQueuePageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminApprovalQueuePageConfig, normalizedItem)
}

export function getAdminApprovalQueuePageConfig(context = {}) {
  const config = [...adminApprovalQueuePageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null

  if (!config) {
    return null
  }

  return {
    ...config,
    noteTemplates: getAdminApprovalQueueNoteTemplates(context),
  }
}

export function registerAdminApprovalQueuePageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminApprovalQueuePageActionMeta, normalizedItem)
}

export function getAdminApprovalQueuePageActionMeta(context = {}) {
  return [...adminApprovalQueuePageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminApprovalQueueNoteTemplate(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminApprovalQueueNoteTemplates, normalizedItem)
}

export function getAdminApprovalQueueNoteTemplates(context = {}) {
  return [...adminApprovalQueueNoteTemplates]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .filter(Boolean)
}

export function registerAdminFlagsPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminFlagsPageCopies, normalizedItem)
}

export function getAdminFlagsPageCopy(context = {}) {
  return [...adminFlagsPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminFlagsPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminFlagsPageConfig, normalizedItem)
}

export function getAdminFlagsPageConfig(context = {}) {
  return [...adminFlagsPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminFlagsPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminFlagsPageActionMeta, normalizedItem)
}

export function getAdminFlagsPageActionMeta(context = {}) {
  return [...adminFlagsPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminPermissionsPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminPermissionsPageCopies, normalizedItem)
}

export function getAdminPermissionsPageCopy(context = {}) {
  return [...adminPermissionsPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminPermissionsPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminPermissionsPageConfig, normalizedItem)
}

export function getAdminPermissionsPageConfig(context = {}) {
  return [...adminPermissionsPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminPermissionsPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminPermissionsPageActionMeta, normalizedItem)
}

export function getAdminPermissionsPageActionMeta(context = {}) {
  return [...adminPermissionsPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminUsersPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminUsersPageCopies, normalizedItem)
}

export function getAdminUsersPageCopy(context = {}) {
  return [...adminUsersPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminUsersPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminUsersPageConfig, normalizedItem)
}

export function getAdminUsersPageConfig(context = {}) {
  return [...adminUsersPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminUsersPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminUsersPageActionMeta, normalizedItem)
}

export function getAdminUsersPageActionMeta(context = {}) {
  return [...adminUsersPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminTagsPageConfig(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminTagsPageConfig, normalizedItem)
}

export function getAdminTagsPageConfig(context = {}) {
  return [...adminTagsPageConfig]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminTagsPageCopy(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminTagsPageCopies, normalizedItem)
}

export function getAdminTagsPageCopy(context = {}) {
  return [...adminTagsPageCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

export function registerAdminTagsPageActionMeta(item) {
  const normalizedItem = {
    order: 100,
    ...item,
  }

  return upsertByKey(adminTagsPageActionMeta, normalizedItem)
}

export function getAdminTagsPageActionMeta(context = {}) {
  return [...adminTagsPageActionMeta]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveAdminItem(item, context))
    .find(Boolean) || null
}

registerAdminRoute({
  path: '/admin',
  name: 'admin-dashboard',
  component: DashboardPage,
  icon: 'fas fa-chart-bar',
  label: '仪表盘',
  navDescription: '查看论坛运行状态、模块概况和系统入口。',
  navSection: 'core',
  navOrder: 10,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/modules',
  name: 'admin-modules',
  component: ModulesPage,
  icon: 'fas fa-cubes',
  label: '模块中心',
  navDescription: '查看内置模块、扩展能力和注册快照。',
  navSection: 'core',
  navOrder: 20,
  showInDashboardActions: true,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/basics',
  name: 'admin-basics',
  component: BasicsPage,
  icon: 'fas fa-pencil-alt',
  label: '基础设置',
  navDescription: '维护论坛标题、公告和基础信息。',
  navSection: 'core',
  navOrder: 30,
  showInDashboardActions: true,
  dashboardActionLabel: '编辑基础设置',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/permissions',
  name: 'admin-permissions',
  component: PermissionsPage,
  icon: 'fas fa-key',
  label: '权限管理',
  navDescription: '管理用户组和访问权限矩阵。',
  navSection: 'core',
  navOrder: 40,
  showInDashboardActions: true,
  dashboardActionLabel: '管理权限',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/appearance',
  name: 'admin-appearance',
  component: AppearancePage,
  icon: 'fas fa-paint-brush',
  label: '外观设置',
  navDescription: '调整主题、Logo 和界面外观。',
  navSection: 'core',
  navOrder: 50,
  showInDashboardActions: true,
  dashboardActionLabel: '自定义外观',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/users',
  name: 'admin-users',
  component: UsersPage,
  icon: 'fas fa-users',
  label: '用户管理',
  navDescription: '查看用户资料、分组和封禁状态。',
  navSection: 'core',
  navOrder: 60,
  showInDashboardActions: true,
  dashboardActionLabel: '管理用户',
  moduleId: 'users'
})

registerAdminRoute({
  path: '/admin/approval',
  name: 'admin-approval',
  component: ApprovalQueuePage,
  icon: 'fas fa-user-check',
  label: '审核队列',
  navDescription: '集中处理待审核讨论和回复。',
  navSection: 'feature',
  navOrder: 110,
  showInDashboardActions: true,
  dashboardActionLabel: '处理审核',
  moduleId: 'approval'
})

registerAdminRoute({
  path: '/admin/flags',
  name: 'admin-flags',
  component: FlagsPage,
  icon: 'fas fa-flag',
  label: '举报管理',
  navDescription: '查看和处理社区举报内容。',
  navSection: 'feature',
  navOrder: 120,
  showInDashboardActions: true,
  dashboardActionLabel: '处理举报',
  moduleId: 'flags'
})

registerAdminRoute({
  path: '/admin/audit-logs',
  name: 'admin-audit-logs',
  component: AuditLogsPage,
  icon: 'fas fa-clipboard-list',
  label: '审计日志',
  navDescription: '追踪后台关键操作记录。',
  navSection: 'feature',
  navOrder: 130,
  showInDashboardActions: true,
  dashboardActionLabel: '查看审计',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/tags',
  name: 'admin-tags',
  component: TagsPage,
  icon: 'fas fa-tags',
  label: '标签管理',
  navDescription: '维护标签结构、排序和可见范围。',
  navSection: 'feature',
  navOrder: 140,
  moduleId: 'tags'
})

registerAdminRoute({
  path: '/admin/mail',
  name: 'admin-mail',
  component: MailPage,
  icon: 'fas fa-envelope',
  label: '邮件设置',
  navDescription: '配置邮件服务和发信能力。',
  navSection: 'feature',
  navOrder: 150,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/advanced',
  name: 'admin-advanced',
  component: AdvancedPage,
  icon: 'fas fa-cog',
  label: '高级设置',
  navDescription: '管理缓存、队列和系统级能力。',
  navSection: 'feature',
  navOrder: 160,
  moduleId: 'core'
})

registerAdminDashboardStat({
  key: 'users',
  order: 10,
  icon: 'fas fa-users',
  moduleId: 'users',
  resolve: ({ stats, copy }) => ({
    label: copy?.usersStatLabel || '用户总数',
    value: stats?.totalUsers || 0,
  }),
})

registerAdminDashboardStat({
  key: 'discussions',
  order: 20,
  icon: 'fas fa-comments',
  moduleId: 'core',
  resolve: ({ stats, copy }) => ({
    label: copy?.discussionsStatLabel || '讨论总数',
    value: stats?.totalDiscussions || 0,
  }),
})

registerAdminDashboardStat({
  key: 'posts',
  order: 30,
  icon: 'fas fa-comment',
  moduleId: 'core',
  resolve: ({ stats, copy }) => ({
    label: copy?.postsStatLabel || '帖子总数',
    value: stats?.totalPosts || 0,
  }),
})

registerAdminDashboardStat({
  key: 'pending-approvals',
  order: 40,
  icon: 'fas fa-user-check',
  iconClass: 'StatsWidget-icon--info',
  moduleId: 'approval',
  resolve: ({ stats, copy }) => ({
    label: copy?.pendingApprovalsStatLabel || '待审核内容',
    value: stats?.pendingApprovals || 0,
  }),
})

registerAdminDashboardStat({
  key: 'open-flags',
  order: 50,
  icon: 'fas fa-flag',
  iconClass: 'StatsWidget-icon--warning',
  moduleId: 'flags',
  resolve: ({ stats, copy }) => ({
    label: copy?.openFlagsStatLabel || '待处理举报',
    value: stats?.openFlags || 0,
  }),
})

registerAdminDashboardStatusSummary({
  key: 'runtime',
  order: 10,
  resolve: ({ stats, copy }) => ({
    label: copy?.runtimeSummaryLabel || '运行时',
    value: stats?.runtimeName || copy?.runtimeNameFallback || 'Python',
    meta: `${copy?.pythonMetaPrefix || 'Python'} ${stats?.pythonVersion || copy?.emptyValueText || '-'}`,
  }),
})

registerAdminDashboardStatusBadge({
  key: 'debug-mode',
  order: 10,
  resolve: ({ stats, copy }) => ({
    text: stats?.debugMode ? (copy?.debugModeOnText || 'DEBUG') : (copy?.debugModeOffText || 'PRODUCTION'),
    tone: stats?.debugMode ? 'warning' : 'success',
  }),
})

registerAdminDashboardStatusBadge({
  key: 'maintenance-mode',
  order: 20,
  resolve: ({ stats, copy }) => ({
    text: stats?.maintenanceMode ? (copy?.maintenanceModeOnText || '维护模式开启') : (copy?.maintenanceModeOffText || '维护模式关闭'),
    tone: stats?.maintenanceMode ? 'warning' : 'neutral',
  }),
})

registerAdminDashboardStatusBadge({
  key: 'redis-status',
  order: 30,
  resolve: ({ stats, copy }) => ({
    text: stats?.redisEnabled ? (copy?.redisEnabledText || 'Redis 已启用') : (copy?.redisDisabledText || 'Redis 未启用'),
    tone: stats?.redisEnabled ? 'success' : 'neutral',
  }),
})

registerAdminDashboardStatusBadge({
  key: 'queue-worker-status',
  order: 40,
  resolve: ({ stats, copy }) => ({
    text: stats?.queueWorkerLabel || copy?.queueWorkerUndetectedText || '队列未检测',
    tone: !stats?.queueEnabled || ['disabled', 'sync'].includes(stats?.queueWorkerStatus)
      ? 'neutral'
      : (stats?.queueWorkerAvailable ? 'success' : 'warning'),
  }),
})

registerAdminDashboardStatusItem({
  key: 'python-version',
  order: 10,
  resolve: ({ stats, copy }) => ({
    label: copy?.pythonVersionLabel || 'Python 版本',
    value: stats?.pythonVersion || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'django-version',
  order: 20,
  resolve: ({ stats, copy }) => ({
    label: copy?.djangoVersionLabel || 'Django 版本',
    value: stats?.djangoVersion || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'database',
  order: 30,
  resolve: ({ stats, copy }) => ({
    label: copy?.databaseLabel || '数据库',
    value: stats?.databaseLabel || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'cache-driver',
  order: 40,
  resolve: ({ stats, copy }) => ({
    label: copy?.cacheDriverLabel || '缓存驱动',
    value: stats?.cacheDriver || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'realtime-driver',
  order: 50,
  resolve: ({ stats, copy }) => ({
    label: copy?.realtimeDriverLabel || '实时层',
    value: stats?.realtimeDriver || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'queue-driver',
  order: 60,
  resolve: ({ stats, copy }) => ({
    label: copy?.queueDriverLabel || '队列执行',
    value: stats?.queueLabel || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'queue-worker',
  order: 70,
  resolve: ({ stats, copy }) => ({
    label: copy?.queueWorkerLabel || '队列 Worker',
    value: stats?.queueWorkerLabel || copy?.emptyValueText || '-',
    help: stats?.queueWorkerMessage || '',
  }),
})

registerAdminDashboardAlert({
  key: 'runtime-risks',
  order: 10,
  isVisible: ({ stats }) => Array.isArray(stats?.runtimeRisks) && stats.runtimeRisks.length > 0,
  resolve: ({ stats, copy }) => {
    const risks = Array.isArray(stats?.runtimeRisks) ? stats.runtimeRisks : []
    return {
      title: copy?.runtimeRiskAlertTitle || '运行时风险提示：',
      tone: risks.some(item => item?.level === 'danger') ? 'danger' : 'warning',
      text: risks.map(item => item.title).join('；'),
    }
  },
})

registerAdminDashboardQueueMetric({
  key: 'queue-enqueued',
  order: 10,
  variant: 'stat',
  resolve: ({ stats, copy }) => ({
    label: copy?.queueEnqueuedLabel || '入队',
    value: stats?.queueMetrics?.enqueued_count || 0,
  }),
})

registerAdminDashboardQueueMetric({
  key: 'queue-sync',
  order: 20,
  variant: 'stat',
  resolve: ({ stats, copy }) => ({
    label: copy?.queueSyncLabel || '同步',
    value: stats?.queueMetrics?.sync_count || 0,
  }),
})

registerAdminDashboardQueueMetric({
  key: 'queue-fallback',
  order: 30,
  variant: 'stat',
  resolve: ({ stats, copy }) => ({
    label: copy?.queueFallbackLabel || '回退',
    value: stats?.queueMetrics?.fallback_count || 0,
  }),
})

registerAdminDashboardQueueMetric({
  key: 'queue-last-task',
  order: 40,
  variant: 'detail',
  resolve: ({ stats, copy }) => ({
    label: copy?.queueLastTaskLabel || '最近任务',
    value: stats?.queueMetrics?.last_task || copy?.emptyValueText || '-',
    error: stats?.queueMetrics?.last_error || '',
  }),
})

registerAdminDashboardCopy({
  key: 'core-dashboard-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '仪表盘',
    pageDescription: '查看论坛概况和系统状态',
    loadingText: '加载中...',
    statusWidgetTitle: '系统状态',
    statsWidgetTitle: '论坛统计',
    actionsWidgetTitle: '快速操作',
    runtimeRiskAlertTitle: '运行时风险提示：',
    runtimeSummaryLabel: '运行时',
    runtimeNameFallback: 'Python',
    pythonMetaPrefix: 'Python',
    debugModeOnText: 'DEBUG',
    debugModeOffText: 'PRODUCTION',
    maintenanceModeOnText: '维护模式开启',
    maintenanceModeOffText: '维护模式关闭',
    redisEnabledText: 'Redis 已启用',
    redisDisabledText: 'Redis 未启用',
    queueWorkerUndetectedText: '队列未检测',
    usersStatLabel: '用户总数',
    discussionsStatLabel: '讨论总数',
    postsStatLabel: '帖子总数',
    pendingApprovalsStatLabel: '待审核内容',
    openFlagsStatLabel: '待处理举报',
    pythonVersionLabel: 'Python 版本',
    djangoVersionLabel: 'Django 版本',
    databaseLabel: '数据库',
    cacheDriverLabel: '缓存驱动',
    realtimeDriverLabel: '实时层',
    queueDriverLabel: '队列执行',
    queueWorkerLabel: '队列 Worker',
    queueEnqueuedLabel: '入队',
    queueSyncLabel: '同步',
    queueFallbackLabel: '回退',
    queueLastTaskLabel: '最近任务',
    emptyValueText: '-',
  }),
})

registerAdminDashboardConfig({
  key: 'core-dashboard-config',
  order: 10,
  resolve: () => ({
    defaultStats: {
      runtimeName: 'Python',
      pythonVersion: null,
      djangoVersion: null,
      databaseLabel: null,
      cacheDriver: null,
      queueDriver: null,
      queueEnabled: false,
      queueLabel: null,
      queueWorkerStatus: 'disabled',
      queueWorkerLabel: null,
      queueWorkerAvailable: false,
      queueWorkerCount: 0,
      queueWorkerMessage: '',
      queueMetrics: {
        enqueued_count: 0,
        sync_count: 0,
        fallback_count: 0,
        last_task: '',
        last_error: '',
        last_event_at: '',
      },
      realtimeDriver: null,
      redisEnabled: false,
      runtimeRisks: [],
      debugMode: false,
      maintenanceMode: false,
      totalUsers: 0,
      totalDiscussions: 0,
      totalPosts: 0,
      pendingApprovals: 0,
      openFlags: 0,
    },
  }),
})

registerAdminDashboardActionMeta({
  key: 'core-dashboard-actions-meta',
  order: 10,
  resolve: () => ({
    loadingErrorText: '加载统计数据失败，请稍后重试',
    queueResetIdleText: '重置指标',
    queueResetPendingText: '重置中...',
    queueResetConfirmTitle: '重置队列指标',
    queueResetConfirmMessage: '确定重置队列运行指标吗？当前累计的入队、同步和回退计数会清零。',
    queueResetConfirmText: '重置',
    queueResetCancelText: '取消',
    queueResetSuccessTitle: '指标已重置',
    queueResetSuccessMessage: '队列运行指标已重置',
    queueResetErrorMessage: '重置失败，请稍后重试',
  }),
})

registerAdminDashboardAction({
  key: 'reset-queue-metrics',
  order: 10,
  resolve: ({ api, modalStore, stats, setStats, setMessage, setMessageTone, setPending, copy }) => ({
    run: async () => {
      const confirmed = await modalStore.confirm({
        title: copy?.queueResetConfirmTitle || '重置队列指标',
        message: copy?.queueResetConfirmMessage || '确定重置队列运行指标吗？当前累计的入队、同步和回退计数会清零。',
        confirmText: copy?.queueResetConfirmText || '重置',
        cancelText: copy?.queueResetCancelText || '取消',
        tone: 'warning'
      })
      if (!confirmed) {
        return
      }

      setPending(true)
      setMessage('')
      setMessageTone('success')

      try {
        const data = await api.post('/admin/queue/metrics/reset')
        setStats({
          ...stats,
          queueMetrics: data.metrics || stats.queueMetrics
        })
        const successMessage = data.message || copy?.queueResetSuccessMessage || '队列运行指标已重置'
        setMessage(successMessage)
        await modalStore.alert({
          title: copy?.queueResetSuccessTitle || '指标已重置',
          message: successMessage,
          tone: 'success'
        })
      } catch (error) {
        console.error('重置队列指标失败:', error)
        setMessageTone('error')
        setMessage(error.response?.data?.error || copy?.queueResetErrorMessage || '重置失败，请稍后重试')
      } finally {
        setPending(false)
      }
    },
  }),
})

registerAdminModulesPageCopy({
  key: 'core-modules-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '模块中心',
    pageDescription: '围绕注册中心查看模块边界、依赖健康、扩展注入面与后台入口。',
    loadingText: '加载模块信息中...',
    dependencyAttentionTitle: '依赖关注项',
    dependencyAttentionDescription: '模块依赖状态会直接影响后续扩展启用与注册结果，这里优先暴露需要处理的项。',
    missingDependenciesPrefix: '缺少依赖',
    disabledDependenciesPrefix: '未启用依赖',
    categorySummaryTitle: '分类概览',
    categorySummaryDescription: '按模块类别查看当前注册规模，优先识别哪些能力已经模块化，哪些区域仍需继续收口。',
    categoryModuleCountText: count => `${count} 个模块`,
    categoryEnabledText: count => `已启用 ${count}`,
    categoryAttentionText: count => `需关注 ${count}`,
    categoryHealthyText: '依赖健康',
    moduleListTitle: '模块列表',
    moduleListDescription: '这里展示内置模块注册结果。当前重点是注册覆盖面、依赖健康和后台接入，不再只是静态清单。',
    searchLabel: '搜索模块',
    searchPlaceholder: '搜索模块名、ID、能力或依赖',
    coreCategoryLabel: '核心',
    enabledStatusLabel: '已启用',
    disabledStatusLabel: '未启用',
    moduleIdLabel: '模块 ID',
    versionLabel: '版本',
    dependenciesLabel: '依赖',
    bootModeLabel: '启动方式',
    settingsGroupLabel: '设置组',
    documentationLabel: '文档',
    settingsEntryActionLabel: '配置入口',
    permissionsEntryActionLabel: '权限入口',
    debugEntryActionLabel: '调试视图',
    documentationEntryActionLabel: '模块文档',
    noValueText: '无',
    staticBootModeLabel: '静态注册',
    adminEntriesTitle: '后台入口',
    permissionsTitle: '权限注册',
    settingsRuntimeTitle: '设置与运行时',
    debugInfoTitle: '调试信息',
    notificationTypesTitle: '通知类型',
    notificationRenderersTitle: '通知渲染器',
    userPreferencesTitle: '用户偏好',
    languagePacksTitle: '语言包',
    eventListenersTitle: '事件监听',
    postTypesTitle: '帖子类型',
    resourceFieldsTitle: '资源字段',
    searchFiltersTitle: '搜索过滤器',
    discussionSortsTitle: '讨论排序',
    discussionListFiltersTitle: '讨论列表过滤',
    settingsGroupItemLabel: '设置组',
    configuredKeyCountLabel: '已配置键',
    migrationStatusLabel: '迁移状态',
    pageSettingsGroupText: group => `设置组: ${group}`,
    noAdminEntriesText: '暂无后台入口',
    noPermissionsText: '暂无权限声明',
    noSettingsRuntimeText: '暂无设置或运行时元数据',
    noDebugInfoText: '暂无调试信息',
    noNotificationTypesText: '暂无通知类型',
    noNotificationRenderersText: '暂无通知渲染器',
    noUserPreferencesText: '暂无用户偏好',
    noLanguagePacksText: '暂无语言包',
    noEventListenersText: '暂无事件监听',
    noPostTypesText: '暂无帖子类型',
    noResourceFieldsText: '暂无资源字段',
    noSearchFiltersText: '暂无搜索过滤器',
    noDiscussionSortsText: '暂无讨论排序',
    noDiscussionListFiltersText: '暂无讨论列表过滤',
    emptyFilteredModulesText: '当前筛选下没有匹配的模块。',
    adminEntriesSectionTitle: '后台注册入口',
    adminEntriesSectionDescription: '按当前筛选结果列出后台页面，便于检查导航是否已经真正从模块注册元数据派生。',
    notificationEventsSectionTitle: '通知类型与事件监听',
    notificationEventsSectionDescription: '用于校验模块通知协议和领域事件挂接是否持续沿统一机制注册。',
    notificationTypesCardTitle: '通知类型',
    notificationTypesCardDescription: '所有已在注册中心声明的站内通知类型。',
    notificationRenderersCardTitle: '通知渲染器',
    notificationRenderersCardDescription: '当前前端已注册的通知展示与跳转 renderer。',
    eventListenersCardTitle: '事件监听器',
    eventListenersCardDescription: '当前模块通过事件总线挂接的监听入口。',
    noEventListenersCardText: '暂无事件监听器',
    userPreferencesSectionTitle: '用户偏好注册',
    userPreferencesSectionDescription: '这里检查模块是否通过统一注册协议声明通知和个性化偏好，而不是散落在页面局部状态中。',
    languagePacksSectionTitle: '语言包注册',
    languagePacksSectionDescription: '列出模块通过注册中心声明的语言包，作为阶段 6 国际化准备的最小快照。',
    postTypesSectionTitle: '帖子类型注册',
    postTypesSectionDescription: '用于承接系统事件帖、状态变更帖和普通回复的统一协议。',
    resourceFieldsSectionTitle: '资源字段注册',
    resourceFieldsSectionDescription: '汇总 Discussion、Post、Tag、Search 等资源上的扩展字段，作为统一 Resource 协议快照。',
    searchFiltersSectionTitle: '搜索过滤器注册',
    searchFiltersSectionDescription: '列出模块通过注册中心声明的搜索过滤语法，帮助检查搜索扩展点的覆盖度。',
    discussionSortsSectionTitle: '讨论排序注册',
    discussionSortsSectionDescription: '列出模块通过注册中心声明的讨论列表排序能力，便于检查论坛首页和标签页的扩展面。',
    discussionListFiltersSectionTitle: '讨论列表过滤注册',
    discussionListFiltersSectionDescription: '列出模块通过注册中心声明的讨论列表过滤能力，帮助检查首页、关注页和用户列表是否正在共用统一协议。',
    adminPageHeader: '页面',
    pathHeader: '路径',
    moduleHeader: '归属模块',
    navSectionHeader: '导航分组',
    coreNavLabel: '核心',
    featureNavLabel: '功能',
    preferenceKeyHeader: '偏好键',
    preferenceCategoryHeader: '分类',
    preferenceDefaultHeader: '默认值',
    descriptionHeader: '说明',
    postTypeCodeHeader: '类型',
    capabilitiesHeader: '能力',
    resourceHeader: '资源',
    fieldHeader: '字段',
    syntaxHeader: '语法',
    targetHeader: '目标资源',
    sortCodeHeader: '排序码',
    nameHeader: '名称',
    defaultHeader: '默认',
    filterCodeHeader: '过滤码',
    requiresAuthHeader: '需登录',
    enabledToggleText: '开启',
    disabledToggleText: '关闭',
    yesText: '是',
    noText: '否',
    resourceFieldFallbackText: '已注册资源扩展字段',
    defaultCapabilityLabel: '默认',
    streamVisibleCapabilityLabel: '帖流可见',
    countsDiscussionCapabilityLabel: '计入讨论',
    countsUserCapabilityLabel: '计入用户',
    searchableCapabilityLabel: '可搜索',
  }),
})

registerAdminModulesPageConfig({
  key: 'core-modules-page-config',
  order: 10,
  resolve: () => ({
    categoryFilterBase: { value: 'all', label: '全部分类', icon: 'fas fa-layer-group' },
    coreCategoryIcon: 'fas fa-shield-alt',
    featureCategoryIcon: 'fas fa-puzzle-piece',
    statusFilterOptions: [
      { value: 'all', label: '全部状态', icon: 'fas fa-border-all' },
      { value: 'healthy', label: '依赖正常', icon: 'fas fa-check-circle' },
      { value: 'attention', label: '需关注', icon: 'fas fa-exclamation-triangle' },
      { value: 'enabled', label: '仅已启用', icon: 'fas fa-toggle-on' },
    ],
    summaryLabels: {
      module_count: '模块总数',
      core_count: '核心模块',
      enabled_count: '已启用',
      dependency_issue_count: '依赖关注',
      permission_count: '权限声明',
      admin_page_count: '后台入口',
      notification_type_count: '通知类型',
      notification_renderer_count: '通知渲染器',
      user_preference_count: '用户偏好',
      language_pack_count: '语言包',
      event_listener_count: '事件监听',
      post_type_count: '帖子类型',
      resource_field_count: '资源字段',
      search_filter_count: '搜索过滤',
      discussion_sort_count: '讨论排序',
      discussion_list_filter_count: '列表过滤',
      settings_group_count: '设置组',
      health_attention_count: '健康关注',
    },
    moduleSummaryLabels: {
      permissions: '权限数',
      admin_pages: '后台页数',
      dependencies: '依赖数',
      capabilities: '能力项',
      notification_types: '通知数',
      notification_renderers: '渲染器',
      user_preferences: '偏好项',
      language_packs: '语言包',
      event_listeners: '监听器',
      post_types: '帖子类型',
      resource_fields: '资源字段',
      search_filters: '搜索过滤',
      discussion_sorts: '讨论排序',
      discussion_list_filters: '列表过滤',
    },
  }),
})

registerAdminModulesPageActionMeta({
  key: 'core-modules-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载模块信息失败，请稍后重试',
  }),
})

registerAdminBasicsPageCopy({
  key: 'core-basics-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '基础设置',
    pageDescription: '配置论坛的基本信息',
    loadingText: '加载基础设置中...',
    forumTitleLabel: '论坛名称',
    forumTitleHelpText: '论坛的名称，显示在页面标题和头部',
    forumDescriptionLabel: '论坛描述',
    forumDescriptionHelpText: '简短描述你的论坛，用于 SEO',
    welcomeSectionTitle: '欢迎区文案',
    welcomeSectionDescription: '首页 Hero 会优先读取这里的标题和说明，作为论坛的默认欢迎语。',
    welcomeTitleLabel: '欢迎标题',
    welcomeMessageLabel: '欢迎说明',
    seoSectionTitle: 'SEO 设置',
    seoSectionDescription: '这些字段会进入公开论坛设置，并在前台页面标题与 meta 标签中生效。',
    seoTitleLabel: 'SEO 标题',
    seoTitleHelpText: '建议控制在 30-60 字符，留空时自动回退到论坛名称。',
    seoDescriptionLabel: 'SEO 描述',
    seoDescriptionHelpText: '建议控制在 80-160 字符，留空时自动回退到论坛描述。',
    seoKeywordsLabel: 'SEO 关键词',
    seoKeywordsHelpText: '使用英文逗号分隔多个关键词，例如：Python, Django, Vue。',
    seoRobotsIndexLabel: '允许搜索引擎建立索引',
    seoRobotsFollowLabel: '允许搜索引擎跟踪页面链接',
    seoNoteText: 'SEO 设置保存后，对外访问的论坛页面通常刷新即可生效；若站点前面接了 CDN 或反向代理缓存，请同步清理缓存。',
    announcementSectionTitle: '站点公告',
    announcementSectionDescription: '在前台顶部展示一条全站公告，适合发布维护预告、运营通知或临时提醒。',
    announcementEnabledLabel: '启用全站公告',
    announcementMessageLabel: '公告内容',
    announcementMessageHelpText: '最多 240 个字符，内容为空时前台不会展示公告。',
    announcementToneLabel: '公告样式',
    defaultLocaleLabel: '默认语言',
    themeModeLabel: '默认主题',
    showLanguageSelectorLabel: '显示语言选择器',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请重试',
  }),
})

registerAdminBasicsPageConfig({
  key: 'core-basics-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      forum_title: '',
      forum_description: '',
      seo_title: '',
      seo_description: '',
      seo_keywords: '',
      seo_robots_index: true,
      seo_robots_follow: true,
      welcome_title: '欢迎来到Bias',
      welcome_message: '这是一个基于Django和Vue 3的现代化论坛',
      announcement_enabled: false,
      announcement_message: '',
      announcement_tone: 'info',
      default_locale: 'zh-CN',
      theme_mode: 'system',
      show_language_selector: false,
    },
    placeholders: {
      forumTitle: '我的论坛',
      forumDescription: '一个很棒的社区',
      welcomeTitle: '欢迎来到 Bias',
      welcomeMessage: '介绍你的社区定位、内容方向或新用户起步方式。',
      seoTitle: '留空时使用论坛名称',
      seoDescription: '留空时使用论坛描述',
      seoKeywords: '论坛, 社区, 技术讨论',
      announcementMessage: '例如：今晚 23:00-23:30 将进行短暂维护。',
    },
    announcementToneOptions: [
      { value: 'info', label: '信息' },
      { value: 'warning', label: '提醒' },
      { value: 'success', label: '成功' },
    ],
    localeOptions: [
      { value: 'zh-CN', label: '简体中文' },
      { value: 'en', label: 'English' },
    ],
    themeModeOptions: [
      { value: 'system', label: '跟随系统' },
      { value: 'light', label: '浅色' },
      { value: 'dark', label: '深色' },
    ],
  }),
})

registerAdminBasicsPageActionMeta({
  key: 'core-basics-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载设置失败，请稍后重试',
  }),
})

registerAdminAppearancePageCopy({
  key: 'core-appearance-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '外观设置',
    pageDescription: '自定义论坛的外观和主题',
    loadingText: '加载外观配置中...',
    colorsSectionTitle: '颜色',
    primaryColorLabel: '主题色',
    primaryColorPickerAriaLabel: '主题色取色器',
    primaryColorHelpText: '论坛的主题颜色',
    accentColorLabel: '强调色',
    accentColorPickerAriaLabel: '强调色取色器',
    accentColorHelpText: '用于按钮和链接的强调色',
    brandingSectionTitle: 'Logo 与图标',
    logoPreviewAlt: 'Logo 预览',
    logoEmptyText: '暂无 Logo',
    logoCardTitle: '站点 Logo',
    logoHelpText: '建议上传透明背景 PNG、SVG 或 WebP，Header 会优先展示这里的资源。',
    logoUploadLabel: '上传本地 Logo',
    logoUploadingLabel: '上传中...',
    clearAssetLabel: '清空',
    logoUrlLabel: 'Logo URL',
    logoUrlHelpText: '论坛 Logo 的 URL 地址',
    faviconPreviewAlt: 'Favicon 预览',
    faviconEmptyText: '暂无 Favicon',
    faviconCardTitle: '浏览器图标',
    faviconHelpText: '建议上传 `.ico`、PNG 或 SVG，小尺寸图标在浏览器标签页里更清晰。',
    faviconUploadLabel: '上传本地 Favicon',
    faviconUploadingLabel: '上传中...',
    faviconUrlLabel: 'Favicon URL',
    faviconUrlHelpText: '浏览器标签页图标的 URL 地址',
    customStyleSectionTitle: '自定义样式',
    presetPanelTitle: '样式预设',
    presetPanelDescription: '点击即可把常用样式片段填入自定义 CSS，你可以继续修改后再保存。',
    clearCssLabel: '清空 CSS',
    customCssLabel: '自定义 CSS',
    customCssHelpText: '添加自定义 CSS 样式来进一步定制论坛外观',
    customHeadLabel: 'Head / 统计代码注入',
    customHeadHelpText: '用于统计脚本、验证标签或其他不直接展示给用户的 Head 注入。',
    customFooterLabel: 'Footer HTML',
    customFooterHelpText: '这里的内容会直接显示在站点页脚，适合备案、版权和联系信息。',
    previewSectionTitle: '实时预览',
    previewPrimaryActionLabel: '主操作',
    previewSecondaryActionLabel: '次操作',
    previewFooterPlaceholder: '页脚自定义内容会显示在这里。',
    previewLogoText: 'Logo',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请重试',
  }),
})

registerAdminAppearancePageConfig({
  key: 'core-appearance-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      primary_color: '#4d698e',
      accent_color: '#e74c3c',
      logo_url: '',
      favicon_url: '',
      custom_css: '',
      custom_head_html: '',
      custom_footer_html: '',
    },
    placeholders: {
      primaryColor: '#4d698e',
      accentColor: '#e74c3c',
      logoUrl: 'https://example.com/logo.png',
      faviconUrl: 'https://example.com/favicon.ico',
      customCss: '/* 在这里添加自定义 CSS */',
      customHead: '<!-- 在这里添加 head 注入或统计代码 -->',
      customFooter: '<p>在页脚展示备案号、版权说明或联系信息</p>',
    },
    uploads: {
      logoAccept: '.png,.jpg,.jpeg,.gif,.webp,.svg',
      faviconAccept: '.ico,.png,.svg,.webp',
    },
    cssPresets: [
      {
        name: '柔和圆角',
        description: '让卡片、按钮和输入框更柔和一些',
        css: `:root {\n  --forum-primary-color: #3f6f90;\n  --forum-accent-color: #d66b4d;\n}\n\n.Button,\n.FormControl,\n.DiscussionListItem,\n.DiscussionHero,\n.PostCard {\n  border-radius: 12px;\n}\n`,
      },
      {
        name: '对比增强',
        description: '提高标题、边框和标签的可读性',
        css: `body {\n  color: #223245;\n}\n\n.Header,\n.DiscussionListItem,\n.PostCard,\n.Sidebar {\n  border-color: #d2dce6;\n}\n\nh1, h2, h3,\n.DiscussionListItem-title {\n  color: #162332;\n}\n`,
      },
      {
        name: '紧凑列表',
        description: '压缩讨论列表和帖子区域的纵向间距',
        css: `.DiscussionListItem,\n.PostCard {\n  padding-top: 12px;\n  padding-bottom: 12px;\n}\n\n.DiscussionHero {\n  padding-top: 20px;\n  padding-bottom: 20px;\n}\n`,
      },
    ],
  }),
})

registerAdminAppearancePageActionMeta({
  key: 'core-appearance-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载外观设置失败，请稍后重试',
    uploadFailedTitle: '上传失败',
    uploadUnknownErrorText: '未知错误',
  }),
})

registerAdminMailPageCopy({
  key: 'core-mail-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '邮件设置',
    pageDescription: '配置 Gmail 或其他 SMTP 服务的发信参数。',
    loadingText: '加载中...',
    sendabilityWarningText: '当前邮件配置尚不可发送。请先补全发件地址和 SMTP 信息。',
    senderSectionTitle: '发件设置',
    senderSectionDescription: '默认按 Gmail SMTP 预填。若使用 Gmail，密码处需要填写应用专用密码。',
    mailFromLabel: '发件地址',
    mailFromHint: '支持 `your@gmail.com` 或 `Bias <your@gmail.com>`。',
    mailHostLabel: 'SMTP 主机',
    mailPortLabel: 'SMTP 端口',
    mailEncryptionLabel: '加密方式',
    mailEncryptionHint: 'Gmail 通常使用 `TLS + 587`。',
    mailFormatLabel: '邮件格式',
    mailFormatHint: '`Multipart` 兼容性最好。',
    mailUsernameLabel: 'SMTP 用户名',
    mailPasswordLabel: 'SMTP 密码',
    mailPasswordHint: '保存后会按当前输入覆盖运行时密码。',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请检查当前配置',
    testSectionTitle: '发送测试邮件',
    testSectionDescription: '优先发送到你填写的测试收件箱。留空时，会回退到当前管理员邮箱。',
    testRecipientLabel: '测试收件箱',
    testRecipientHint: '建议填写一个真实可收信邮箱，便于直接验证 SMTP 是否可用。',
    effectiveRecipientPrefix: '实际发送到：',
    effectiveRecipientEmptyText: '（未设置）',
    unsavedChangesHint: '请先保存当前修改，再发送测试邮件。',
    testSendLabel: '发送测试邮件',
    testSendingLabel: '发送中...',
  }),
})

registerAdminMailPageConfig({
  key: 'core-mail-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      mail_from: '',
      mail_format: 'multipart',
      mail_host: 'smtp.gmail.com',
      mail_port: 587,
      mail_encryption: 'tls',
      mail_username: '',
      mail_password: '',
      mail_test_recipient: '',
    },
    placeholders: {
      mailFrom: 'Bias <your@gmail.com>',
      mailHost: 'smtp.gmail.com',
      mailPort: '587',
      mailUsername: 'your@gmail.com',
      mailPassword: '应用专用密码',
      mailTestRecipient: 'admin@example.com',
    },
    encryptionOptions: [
      { value: '', label: '无' },
      { value: 'tls', label: 'TLS' },
      { value: 'ssl', label: 'SSL' },
    ],
    formatOptions: [
      { value: 'multipart', label: 'Multipart' },
      { value: 'plain', label: 'Plain Text' },
      { value: 'html', label: 'HTML' },
    ],
  }),
})

registerAdminMailPageActionMeta({
  key: 'core-mail-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载邮件设置失败，请稍后重试',
    testSuccessTitle: '测试邮件已发送',
    testSuccessMessage: toEmail => `测试邮件已发送到 ${toEmail}，请检查收件箱`,
    testFailedTitle: '发送测试邮件失败',
    unknownErrorText: '未知错误',
  }),
})

registerAdminAdvancedPageCopy({
  key: 'core-advanced-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '高级设置',
    pageDescription: '配置缓存、队列、维护模式与文件存储',
    runtimeNoticeTitle: '运行时说明',
    immediateEffectTitle: '即时生效',
    immediateEffectDescription: '`maintenance_mode`、`maintenance_message`、`cache_lifetime`、`log_queries` 会在保存后直接影响请求层行为。',
    deploymentRequiredTitle: '需额外部署或重启',
    deploymentRequiredDescription: '`debug_mode` 由 Django 配置文件或环境变量控制；`queue_enabled` / `queue_driver` 会控制已接入队列入口的任务，新 worker 配置需重启服务后生效。',
    cacheSectionTitle: '缓存设置',
    cacheDriverLabel: '缓存驱动',
    cacheDriverHelpText: '选择缓存存储方式',
    cacheLifetimeLabel: '缓存时间（秒）',
    cacheLifetimeHelpText: '当前已接入公开论坛设置缓存。填 0 表示禁用该缓存，保存基础/外观/高级设置时会自动清理。',
    clearCacheLabel: '清除缓存',
    clearingCacheLabel: '清除中...',
    searchSectionTitle: '搜索索引',
    searchStatusLabel: '当前状态',
    searchStatusHintText: '查看当前索引与队列运行状态。',
    searchStatusLoadingText: '加载中...',
    searchDatabaseLabel: '当前数据库',
    searchLastRebuildLabel: '最近重建',
    searchNeverRebuiltText: '尚未重建',
    searchLastRebuildDurationFallback: '最近一次重建未记录耗时。',
    searchLastRebuildDurationText: durationMs => `最近一次耗时 ${durationMs} ms`,
    searchQueueStatusLabel: '索引队列状态',
    searchQueueStatusHelpText: '当前重建按钮仍是请求内执行，后续异步索引任务会复用这里的队列运行状态。',
    searchMissingIndexesLabel: '缺失索引',
    searchIndexLabel: 'PostgreSQL 全文索引',
    searchIndexHelpText: '用于英文、数字关键词的讨论、回复和用户搜索。数据量较大时请在低峰期执行。',
    rebuildSearchIndexesLabel: '重建搜索索引',
    rebuildingSearchIndexesLabel: '重建中...',
    queueSectionTitle: '队列设置',
    queueDriverLabel: '队列驱动',
    queueDriverHelpText: '当前通知实时投递已接入统一队列入口。选择 Redis 并部署 worker 后会尝试异步投递。',
    queueEnabledLabel: '启用队列处理',
    queueEnabledHelpText: '关闭时强制同步执行。开启后，已接入任务会入队执行；入队失败时会同步回退，避免影响主流程。',
    realtimeTypingEnabledLabel: '启用回复输入提示',
    realtimeTypingEnabledHelpText: '关闭后，讨论详情页不再广播“正在输入”状态；仍保留其他实时通知与更新。',
    humanVerificationSectionTitle: '安全与真人验证',
    humanVerificationProviderLabel: '验证提供方',
    humanVerificationProviderHelpText: '建议正式环境开启，优先拦截登录和注册机器人。',
    turnstileSiteKeyLabel: 'Site Key',
    turnstileSecretKeyLabel: 'Secret Key',
    turnstileLoginEnabledLabel: '登录时启用真人验证',
    turnstileRegisterEnabledLabel: '注册时启用真人验证',
    turnstileMisconfiguredText: '已选择 Turnstile，但 Site Key 或 Secret Key 仍为空，当前不会真正启用验证。',
    storageSectionTitle: '文件存储',
    storageDriverLabel: '存储驱动',
    storageDriverHelpText: 'Composer 上传、头像上传和后续附件能力都会读取这里的运行时配置',
    storageAttachmentsDirLabel: '附件目录',
    storageAttachmentsDirHelpText: '统一的附件对象目录，支持多级路径',
    storageAvatarsDirLabel: '头像目录',
    storageAvatarsDirHelpText: '头像和缩略图的对象目录',
    uploadPolicyTitle: '上传策略',
    uploadPolicyDescription: '限制上传大小，扩展名白名单仍由服务端固定控制。',
    uploadAvatarMaxSizeLabel: '头像最大体积（MB）',
    uploadAttachmentMaxSizeLabel: '附件最大体积（MB）',
    uploadSiteAssetMaxSizeLabel: '站点资源最大体积（MB）',
    uploadSizeHelpText: '头像默认 2MB，Composer 附件默认 10MB，Logo/Favicon 默认 2MB。',
    localPathLabel: '本地保存目录',
    localPathHelpText: '可填写绝对路径，也可填写相对项目根目录的路径',
    localBaseUrlLabel: '本地访问基地址',
    localBaseUrlHelpText: '上传完成后生成给前台的 URL 前缀',
    bucketLabel: 'Bucket',
    regionLabel: 'Region',
    endpointLabel: 'Endpoint',
    publicUrlLabel: '公共访问 URL',
    publicUrlCdnLabel: '公共访问 URL / CDN 域名',
    s3EndpointHelpText: '使用 MinIO、Wasabi 等兼容服务时填写自定义 Endpoint',
    s3PublicUrlHelpText: '如留空，系统会按标准 S3 域名尝试拼接',
    accessKeyIdLabel: 'Access Key ID',
    secretAccessKeyLabel: 'Secret Access Key',
    accessKeySecretLabel: 'Access Key Secret',
    objectPrefixLabel: '对象前缀',
    pathStyleLabel: '使用 Path Style',
    pathStyleHelpText: '兼容部分 S3 服务或自建对象存储',
    r2PublicUrlHelpText: 'R2 通常需要单独的公开域名，否则前台生成的附件链接不可访问',
    ossPublicUrlHelpText: '如留空，将按 Bucket + Endpoint 生成标准 OSS 访问地址',
    imagebedEndpointLabel: '上传接口地址',
    imagebedMethodLabel: '请求方法',
    imagebedFileFieldLabel: '文件字段名',
    imagebedUrlPathLabel: '响应 URL 路径',
    imagebedUrlPathHelpText: '支持点路径，例如 `data.url`、`result.images.0.url`',
    imagebedHeadersLabel: '请求头 JSON',
    imagebedFormDataLabel: '额外表单参数 JSON',
    maintenanceSectionTitle: '维护模式',
    maintenanceEnabledLabel: '启用维护模式',
    maintenanceEnabledHelpText: '启用后，普通用户访问论坛 API 将收到 503；`/api/forum`、登录接口和后台入口保留豁免。',
    maintenanceMessageLabel: '维护提示信息',
    debugSectionTitle: '调试设置',
    debugModeLabel: '调试模式（只读）',
    debugModeHelpText: '当前运行值来自 Django 配置文件或环境变量，保存这里不会热切换服务端 DEBUG。',
    logQueriesLabel: '记录数据库查询',
    logQueriesHelpText: '保存后即时生效。会把每个 HTTP 请求触发的 SQL 记录到服务器日志。',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请重试',
  }),
})

registerAdminAdvancedPageConfig({
  key: 'core-advanced-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      cache_driver: 'file',
      cache_lifetime: 3600,
      queue_driver: 'sync',
      queue_enabled: false,
      realtime_typing_enabled: true,
      maintenance_mode: false,
      maintenance_message: '',
      debug_mode: false,
      log_queries: false,
      auth_human_verification_provider: 'off',
      auth_turnstile_site_key: '',
      auth_turnstile_secret_key: '',
      auth_human_verification_login_enabled: true,
      auth_human_verification_register_enabled: true,
      storage_driver: 'local',
      storage_attachments_dir: 'attachments',
      storage_avatars_dir: 'avatars',
      upload_avatar_max_size_mb: 2,
      upload_attachment_max_size_mb: 10,
      upload_site_asset_max_size_mb: 2,
      storage_local_path: '',
      storage_local_base_url: '/media/',
      storage_s3_bucket: '',
      storage_s3_region: '',
      storage_s3_endpoint: '',
      storage_s3_access_key_id: '',
      storage_s3_secret_access_key: '',
      storage_s3_public_url: '',
      storage_s3_object_prefix: '',
      storage_s3_path_style: false,
      storage_r2_bucket: '',
      storage_r2_endpoint: '',
      storage_r2_access_key_id: '',
      storage_r2_secret_access_key: '',
      storage_r2_public_url: '',
      storage_r2_object_prefix: '',
      storage_oss_bucket: '',
      storage_oss_endpoint: '',
      storage_oss_access_key_id: '',
      storage_oss_access_key_secret: '',
      storage_oss_public_url: '',
      storage_oss_object_prefix: '',
      storage_imagebed_endpoint: '',
      storage_imagebed_method: 'POST',
      storage_imagebed_file_field: 'file',
      storage_imagebed_headers: '{}',
      storage_imagebed_form_data: '{}',
      storage_imagebed_url_path: 'data.url',
    },
    placeholders: {
      cacheLifetime: '3600',
      turnstileSiteKey: '0x4AAAA...',
      turnstileSecretKey: '0x4AAAA...',
      storageAttachmentsDir: 'attachments',
      storageAvatarsDir: 'avatars',
      storageLocalPath: 'D:\\data\\bias\\media',
      storageLocalBaseUrl: '/media/',
      storageS3Region: 'ap-southeast-1',
      storageS3Endpoint: 'https://s3.amazonaws.com',
      storageS3PublicUrl: 'https://cdn.example.com',
      storageObjectPrefix: 'bias',
      storageR2Endpoint: 'https://<accountid>.r2.cloudflarestorage.com',
      storageR2PublicUrl: 'https://pub-xxx.r2.dev',
      storageOssEndpoint: 'oss-cn-hangzhou.aliyuncs.com',
      imagebedEndpoint: 'https://example.com/api/upload',
      imagebedFileField: 'file',
      imagebedUrlPath: 'data.url',
      imagebedHeaders: '{"Authorization":"Bearer token"}',
      imagebedFormData: '{"album":"forum"}',
      maintenanceMessage: '论坛正在维护中，请稍后再试...',
    },
    cacheDriverOptions: [
      { value: 'file', label: '文件' },
      { value: 'redis', label: 'Redis' },
      { value: 'memcached', label: 'Memcached' },
    ],
    queueDriverOptions: [
      { value: 'sync', label: '同步' },
      { value: 'database', label: '数据库' },
      { value: 'redis', label: 'Redis' },
    ],
    humanVerificationProviderOptions: [
      { value: 'off', label: '关闭' },
      { value: 'turnstile', label: 'Cloudflare Turnstile' },
    ],
    storageDriverOptions: [
      { value: 'local', label: '本地存储' },
      { value: 's3', label: 'Amazon S3 / S3 兼容' },
      { value: 'r2', label: 'Cloudflare R2' },
      { value: 'oss', label: '阿里云 OSS' },
      { value: 'imagebed', label: '通用图床' },
    ],
    imagebedMethodOptions: [
      { value: 'POST', label: 'POST' },
      { value: 'PUT', label: 'PUT' },
      { value: 'PATCH', label: 'PATCH' },
    ],
    sensitiveLabels: {
      maintenance_mode: '维护模式',
      queue_enabled: '队列启用状态',
      realtime_typing_enabled: '回复输入提示',
      queue_driver: '队列驱动',
      log_queries: 'SQL 查询日志',
      storage_driver: '文件存储驱动',
      upload_avatar_max_size_mb: '头像上传上限',
      upload_attachment_max_size_mb: '附件上传上限',
      upload_site_asset_max_size_mb: '站点资源上传上限',
    },
  }),
})

registerAdminAdvancedPageActionMeta({
  key: 'core-advanced-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载高级设置失败，请稍后重试',
    saveConfirmTitle: '保存高级设置',
    saveConfirmMessage: changes => `以下设置会影响运行时行为：${changes.join('、')}。确定保存当前配置吗？`,
    saveConfirmText: '保存',
    saveCancelText: '取消',
    clearCacheConfirmTitle: '清除缓存',
    clearCacheConfirmMessage: '确定清除运行时缓存吗？短时间内部分页面可能重新读取配置和数据。',
    clearCacheConfirmText: '清除',
    clearCacheCancelText: '取消',
    clearCacheSuccessTitle: '缓存已清除',
    clearCacheSuccessMessage: '运行时缓存已成功清理。',
    clearCacheFailedTitle: '清除缓存失败',
    loadSearchStatusErrorText: '加载搜索索引状态失败，请稍后重试',
    rebuildSearchConfirmTitle: '重建搜索索引',
    rebuildSearchConfirmMessage: '确定在后台重建 PostgreSQL 全文搜索索引吗？数据量较大时可能耗时较长，建议在低峰期执行。',
    rebuildSearchConfirmText: '重建',
    rebuildSearchCancelText: '取消',
    rebuildSearchSuccessTitle: '搜索索引已重建',
    rebuildSearchSuccessMessage: result => `已重建 ${Array.isArray(result?.indexes) ? result.indexes.length : 0} 个搜索索引。`,
    rebuildSearchFailedTitle: '重建搜索索引失败',
    unknownErrorText: '未知错误',
  }),
})

registerAdminTagsPageCopy({
  key: 'core-tags-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '标签管理',
    pageDescription: '管理讨论标签和分类',
    createLabel: '创建标签',
    refreshLabel: '刷新统计',
    refreshingLabel: '刷新中...',
    loadingText: '加载中...',
    emptyText: '暂无标签',
    previewLabel: '实时预览',
    previewRootText: '当前会作为顶级标签显示在列表中。',
    previewChildText: '当前会作为子标签显示在父标签下方。',
    previewFallbackName: '新标签',
    modalCreateTitle: '创建标签',
    modalEditTitle: '编辑标签',
    modalSubtitle: '参考 Flarum 的标签编辑流程，并补齐父子层级、排序和显示状态配置。',
    tablePreviewHeader: '预览',
    tableNameHeader: '标签名称',
    tableSlugHeader: '别名',
    tableHierarchyHeader: '层级',
    tableStatusHeader: '状态',
    tableDiscussionCountHeader: '讨论数',
    tableActionHeader: '操作',
    nameLabel: '标签名称 *',
    namePlaceholder: '例如：技术讨论',
    slugLabel: '别名 / Slug',
    slugPlaceholder: '例如：tech-talk',
    slugHelpText: '留空时自动生成，建议使用短横线风格。',
    descriptionLabel: '描述',
    descriptionPlaceholder: '标签的简短描述',
    parentLabel: '父标签',
    parentRootOptionLabel: '作为顶级标签',
    parentHelpText: '只能选择顶级标签作为父标签；设置后，这个标签会显示在对应父标签下方。',
    parentChildrenBlockedText: '当前标签下已有子标签，不能再把它设为次标签。',
    positionLabel: '排序位置',
    positionPlaceholder: '0',
    positionHelpTextPrefix: '数字越小越靠前',
    positionHelpRootText: '顶级标签层',
    positionHelpParentText: '当前父标签下',
    colorLabel: '颜色',
    colorPlaceholder: '#888888',
    colorPickerAriaLabel: '标签颜色选择器',
    iconLabel: '图标',
    clearIconLabel: '清除图标',
    iconSearchPlaceholder: '搜索图标，例如 code、comments、tag',
    iconNoMatchText: '没有找到匹配的图标',
    iconHelpText: '标签仍然保存为 Font Awesome 类名，但现在可以直接搜索和点选。',
    iconManualLabel: '手动输入图标类名',
    iconManualPlaceholder: '高级模式：手动输入 Font Awesome 类名',
    visibilityLabel: '显示与发帖限制',
    hiddenLabel: '隐藏标签',
    restrictedLabel: '限制发帖',
    viewScopeLabel: '查看权限',
    startScopeLabel: '发帖权限',
    replyScopeLabel: '回帖权限',
    startScopeHelpText: '发帖权限不能比查看权限更宽松。',
    restrictedHelpText: '“限制发帖”开启后，普通用户无法在该标签下发起讨论；回帖权限仍按这里的配置生效。',
    postingHelpText: '标签级权限会作用到讨论列表、详情页、发帖和回帖流程。',
    editLabel: '编辑',
    moveUpLabel: '上移',
    moveDownLabel: '下移',
    deleteLabel: '删除',
    saveLabel: '保存',
    savingLabel: '保存中...',
    cancelLabel: '取消',
    tagPreviewCardLabel: '实时预览',
    tagPreviewRootText: '当前会作为顶级标签显示在列表中。',
    tagPreviewChildText: '当前会作为子标签显示在父标签下方。',
    sortTextPrefix: '排序',
    rootLevelText: '顶级标签',
    childLevelText: '子标签',
    childOwnedPrefix: '隶属',
    viewTextPrefix: '查看',
    startTextPrefix: '发帖',
    replyTextPrefix: '回帖',
    publicText: '公开',
    summaryTagTotalLabel: '标签总数',
    summaryTagHierarchyLabel: '顶级 / 子标签',
    summaryHiddenLabel: '隐藏标签',
    summaryRestrictedLabel: '限制发帖',
    configHierarchyLabel: '层级',
    configSortLabel: '排序',
    configViewLabel: '查看范围',
    configPostingLabel: '发帖 / 回帖',
  }),
})

registerAdminTagsPageConfig({
  key: 'core-tags-page-config',
  order: 10,
  resolve: () => ({
    colorPresets: [
      '#3c78d8',
      '#4d698e',
      '#0e7490',
      '#0f766e',
      '#2f855a',
      '#65a30d',
      '#ca8a04',
      '#ea580c',
      '#dc2626',
      '#c026d3',
      '#7c3aed',
      '#475569',
    ],
    scopeOptions: [
      { value: 'public', label: '所有人' },
      { value: 'members', label: '已登录用户' },
      { value: 'staff', label: '仅管理员' },
    ],
    iconOptions: [
      { value: 'fas fa-comments', label: '讨论' },
      { value: 'fas fa-comment-dots', label: '对话' },
      { value: 'fas fa-code', label: '代码' },
      { value: 'fas fa-terminal', label: '终端' },
      { value: 'fas fa-bug', label: '问题' },
      { value: 'fas fa-lightbulb', label: '想法' },
      { value: 'fas fa-rocket', label: '发布' },
      { value: 'fas fa-book', label: '文档' },
      { value: 'fas fa-graduation-cap', label: '教程' },
      { value: 'fas fa-wrench', label: '工具' },
      { value: 'fas fa-cubes', label: '框架' },
      { value: 'fas fa-plug', label: '插件' },
      { value: 'fas fa-cloud', label: '云服务' },
      { value: 'fas fa-server', label: '服务端' },
      { value: 'fas fa-database', label: '数据库' },
      { value: 'fas fa-shield-alt', label: '安全' },
      { value: 'fas fa-mobile-alt', label: '移动端' },
      { value: 'fas fa-desktop', label: '桌面端' },
      { value: 'fas fa-image', label: '图片' },
      { value: 'fas fa-video', label: '视频' },
      { value: 'fas fa-music', label: '音频' },
      { value: 'fas fa-gamepad', label: '游戏' },
      { value: 'fas fa-briefcase', label: '工作' },
      { value: 'fas fa-chart-line', label: '增长' },
      { value: 'fas fa-bullhorn', label: '公告' },
      { value: 'fas fa-fire', label: '热门' },
      { value: 'fas fa-star', label: '精选' },
      { value: 'fas fa-heart', label: '喜欢' },
      { value: 'fas fa-users', label: '社区' },
      { value: 'fas fa-user-shield', label: '管理' },
      { value: 'fas fa-tags', label: '标签' },
      { value: 'fas fa-thumbtack', label: '置顶' },
      { value: 'fas fa-lock', label: '锁定' },
      { value: 'fas fa-language', label: '语言' },
      { value: 'fas fa-globe', label: '全球' },
      { value: 'fas fa-seedling', label: '新手' },
    ],
  }),
})

registerAdminTagsPageActionMeta({
  key: 'core-tags-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载标签失败，请稍后重试',
    saveIncompleteTitle: '信息不完整',
    saveIncompleteMessage: '请输入标签名称',
    saveFailedTitle: '保存失败',
    saveUnknownErrorText: '未知错误',
    deleteConfirmTitle: '删除标签',
    deleteConfirmMessage: tag => `确定要删除标签“${tag}”吗？`,
    deleteConfirmText: '删除',
    deleteCancelText: '取消',
    deleteSuccessTitle: '标签已删除',
    deleteSuccessMessage: tag => `标签“${tag}”已删除。`,
    deleteFailedTitle: '删除失败',
    deleteFailedMessage: '未知错误',
    refreshConfirmTitle: '刷新标签统计',
    refreshConfirmMessage: '确定刷新全部标签的讨论数和最后发帖信息吗？数据量较大时建议在低峰期执行。',
    refreshConfirmText: '刷新',
    refreshCancelText: '取消',
    refreshFailedTitle: '刷新标签统计失败',
    refreshFailedMessage: '未知错误',
    moveFailedTitle: '调整排序失败',
    moveFailedMessage: '未知错误',
  }),
})

registerAdminAuditLogsPageCopy({
  key: 'core-audit-logs-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '审计日志',
    pageDescription: '查看管理员关键操作记录',
    actionFilterLabel: '筛选操作',
    targetFilterLabel: '筛选对象',
    allActionsLabel: '全部操作',
    allTargetsLabel: '全部对象',
    refreshLabel: '刷新',
    loadingText: '加载中...',
    loadErrorText: '加载审计日志失败',
    emptyText: '暂无审计日志',
    tableTimeHeader: '时间',
    tableUserHeader: '管理员',
    tableActionHeader: '操作',
    tableTargetHeader: '对象',
    tableSourceHeader: '来源',
    tableDetailHeader: '详情',
    timeLabel: '时间',
    userLabel: '管理员',
    actionLabel: '操作',
    targetLabel: '对象',
    sourceLabel: '来源',
    detailLabel: '详情',
    systemUserLabel: '系统',
    unknownActionLabel: '未知操作',
  }),
})

registerAdminAuditLogsPageConfig({
  key: 'core-audit-logs-page-config',
  order: 10,
  resolve: () => ({
    actionLabels: {
      'admin.appearance_asset.upload': '上传外观资源',
      'admin.approval.approve': '审核通过',
      'admin.approval.reject': '审核拒绝',
      'admin.cache.clear': '清除缓存',
      'admin.discussion.delete': '删除讨论',
      'admin.discussion.hide': '隐藏讨论',
      'admin.discussion.lock': '锁定讨论',
      'admin.discussion.restore': '恢复讨论',
      'admin.discussion.sticky': '置顶讨论',
      'admin.discussion.unlock': '解锁讨论',
      'admin.discussion.unsticky': '取消置顶',
      'admin.flag.resolve': '处理举报',
      'admin.group.create': '创建用户组',
      'admin.group.delete': '删除用户组',
      'admin.group.update': '更新用户组',
      'admin.mail.test': '发送测试邮件',
      'admin.permissions.update': '更新权限',
      'admin.post.delete': '删除回复',
      'admin.post.hide': '隐藏回复',
      'admin.post.restore': '恢复回复',
      'admin.queue_metrics.reset': '重置队列指标',
      'admin.search_indexes.rebuild': '重建搜索索引',
      'admin.settings.update': '更新设置',
      'admin.tag.create': '创建标签',
      'admin.tag.delete': '删除标签',
      'admin.tag.move': '移动标签',
      'admin.tag.refresh_stats': '刷新标签统计',
      'admin.tag.update': '更新标签',
      'admin.user.delete': '删除用户',
      'admin.user.update': '更新用户',
    },
    targetLabels: {
      appearance_asset: '外观资源',
      cache: '缓存',
      discussion: '讨论',
      group: '用户组',
      mail: '邮件',
      search_index: '搜索索引',
      permissions: '权限',
      post: '回复',
      post_flag: '举报',
      settings: '设置',
      tag: '标签',
      user: '用户',
    },
  }),
})

registerAdminApprovalQueuePageCopy({
  key: 'core-approval-queue-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '审核队列',
    pageDescription: '审核未验证邮箱用户提交的讨论和回复',
    loadingText: '加载中...',
    emptyText: '当前没有待审核内容',
    discussionTypeLabel: '讨论',
    postTypeLabel: '回复',
    unknownAuthorLabel: '未知',
    authorPrefix: '作者',
    submittedAtPrefix: '提交于',
    floorPrefix: '楼层',
    viewContentLabel: '查看内容',
    emptyContentText: '暂无正文内容',
    approveLabel: '审核通过',
    rejectLabel: '拒绝并隐藏',
    selectAllLabel: '全选当前列表',
    selectItemLabel: '选择此项',
    bulkApproveLabel: '批量通过',
    bulkRejectLabel: '批量拒绝',
    clearSelectionLabel: '清空选择',
    bulkSelectionSummary: count => `已选择 ${count} 项`,
    modalApproveTitle: '审核通过',
    modalRejectTitle: '拒绝内容',
    modalApproveDescription: '通过后内容会对有权限的用户可见。',
    modalRejectDescription: '拒绝后作者仍可看到审核反馈。',
    noteLabel: '审核备注',
    noteTemplatesLabel: '常用模板',
    noteTemplatesHint: '点击可快速填入审核反馈，你仍可继续修改。',
    approveNotePlaceholder: '例如：内容符合社区规范，已放行',
    rejectNotePlaceholder: '例如：内容质量不足，已拒绝',
    confirmApproveText: '通过审核',
    confirmRejectText: '拒绝并隐藏',
    bulkApproveConfirmTitle: '批量通过审核',
    bulkRejectConfirmTitle: '批量拒绝内容',
    bulkApproveConfirmMessage: count => `确定批量通过这 ${count} 条待审核内容吗？`,
    bulkRejectConfirmMessage: count => `确定批量拒绝这 ${count} 条待审核内容吗？`,
    bulkApproveConfirmText: '批量通过',
    bulkRejectConfirmText: '批量拒绝',
    bulkActionCancelText: '取消',
    unknownTimeText: '未知时间',
  }),
})

registerAdminApprovalQueuePageConfig({
  key: 'core-approval-queue-page-config',
  order: 10,
  resolve: () => ({
    filters: [
      { value: 'all', label: '全部', icon: 'fas fa-layer-group' },
      { value: 'discussion', label: '讨论', icon: 'fas fa-comments' },
      { value: 'post', label: '回复', icon: 'fas fa-reply' },
    ],
  }),
})

registerAdminApprovalQueuePageActionMeta({
  key: 'core-approval-queue-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载审核队列失败，请稍后重试',
    approveSuccessTitle: '审核已通过',
    approveSuccessMessage: '内容已放行，用户现在可以正常查看。',
    rejectSuccessTitle: '内容已拒绝',
    rejectSuccessMessage: '内容已拒绝并隐藏。',
    bulkApproveSuccessTitle: '批量审核已通过',
    bulkApproveSuccessMessage: count => `已批量通过 ${count} 条内容。`,
    bulkRejectSuccessTitle: '批量拒绝已完成',
    bulkRejectSuccessMessage: count => `已批量拒绝 ${count} 条内容。`,
    submitFailedTitle: '提交失败',
    submitFailedMessage: '未知错误',
  }),
})

registerAdminApprovalQueueNoteTemplate({
  key: 'approval-approve-compliant',
  order: 10,
  resolve: () => ({
    label: '内容符合规范',
    value: '内容符合社区规范，已放行。',
    description: '适用于无需额外修改的通过场景。',
    actions: ['approve'],
  }),
})

registerAdminApprovalQueueNoteTemplate({
  key: 'approval-approve-context-complete',
  order: 20,
  resolve: () => ({
    label: '补充后通过',
    value: '已补充必要上下文，现已通过审核。',
    description: '适用于作者补充说明后的放行场景。',
    actions: ['approve'],
  }),
})

registerAdminApprovalQueueNoteTemplate({
  key: 'approval-reject-quality',
  order: 30,
  resolve: () => ({
    label: '内容质量不足',
    value: '内容质量不足，请补充更完整的信息后重新提交。',
    description: '适用于讨论或回复内容过短、信息不足的场景。',
    actions: ['reject'],
  }),
})

registerAdminApprovalQueueNoteTemplate({
  key: 'approval-reject-duplicate',
  order: 40,
  resolve: () => ({
    label: '重复内容',
    value: '内容与现有讨论重复，请优先在已有主题下继续交流。',
    description: '适用于重复发帖或重复回复场景。',
    actions: ['reject'],
    itemTypes: ['discussion', 'post'],
  }),
})

registerAdminApprovalQueueNoteTemplate({
  key: 'approval-reject-format',
  order: 50,
  resolve: () => ({
    label: '表达不完整',
    value: '表达不完整或缺少必要上下文，请整理后重新提交。',
    description: '适用于语义不清、缺少上下文的场景。',
    actions: ['reject'],
  }),
})

registerAdminFlagsPageCopy({
  key: 'core-flags-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '举报管理',
    pageDescription: '处理用户提交的帖子举报',
    loadingText: '加载中...',
    emptyText: '暂无举报记录',
    reporterPrefix: '举报人',
    discussionPrefix: '讨论',
    postPrefix: '帖子',
    viewPostLabel: '查看帖子',
    reasonBlockTitle: '举报说明',
    postBlockTitle: '帖子内容',
    emptyReasonText: '用户未填写补充说明',
    resolveLabel: '标记已处理',
    ignoreLabel: '忽略举报',
    resolverPrefix: '处理人',
    resolutionNotePrefix: '备注',
    unknownResolverLabel: '未知',
    statusOpenLabel: '待处理',
    statusResolvedLabel: '已处理',
    statusIgnoredLabel: '已忽略',
    modalResolveTitle: '标记举报已处理',
    modalIgnoreTitle: '忽略举报',
    modalResolveDescription: '标记后这条举报会从待处理列表移出。',
    modalIgnoreDescription: '忽略后举报会进入已忽略列表，便于后续追溯。',
    noteLabel: '处理备注',
    resolveNotePlaceholder: '例如：已隐藏帖子并警告用户',
    ignoreNotePlaceholder: '例如：举报理由不足，暂不处理',
  }),
})

registerAdminFlagsPageConfig({
  key: 'core-flags-page-config',
  order: 10,
  resolve: () => ({
    filters: [
      { value: 'open', label: '待处理', icon: 'fas fa-inbox' },
      { value: 'resolved', label: '已处理', icon: 'fas fa-check-circle' },
      { value: 'ignored', label: '已忽略', icon: 'fas fa-ban' },
    ],
  }),
})

registerAdminFlagsPageActionMeta({
  key: 'core-flags-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载举报失败，请稍后重试',
    resolveSuccessTitle: '举报已处理',
    resolveSuccessMessage: '举报状态已更新为已处理。',
    ignoreSuccessTitle: '举报已忽略',
    ignoreSuccessMessage: '举报状态已更新为已忽略。',
    resolveFailedTitle: '处理失败',
    resolveFailedMessage: '未知错误',
  }),
})

registerAdminPermissionsPageCopy({
  key: 'core-permissions-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '权限管理',
    pageDescription: '配置用户组和权限，并检查权限来源与依赖关系',
    metaSummaryText: ({ permissionCount, moduleCount }) => `当前共注册 ${permissionCount} 项权限，来自 ${moduleCount} 个模块。保存时会自动补齐依赖权限，避免出现“子权限已勾选但前置权限缺失”的配置。`,
    editGroupTitle: '编辑用户组',
    addGroupLabel: '添加用户组',
    permissionHeaderLabel: '权限',
    dependencyPrefix: '依赖',
    mobilePermissionCountText: count => `${count} 项权限`,
    savePermissionsLabel: '保存权限',
    savingPermissionsLabel: '保存中...',
    saveSuccessText: '保存成功',
    createGroupTitle: '创建用户组',
    updateGroupTitle: '编辑用户组',
    groupNameLabel: '名称',
    groupNamePlaceholder: '例如：Moderator',
    groupIconLabel: '图标',
    groupIconPlaceholder: '例如：fas fa-shield-alt',
    groupColorLabel: '颜色',
    groupColorPickerAriaLabel: '用户组颜色选择器',
    groupColorPlaceholder: '#4d698e',
    groupHiddenLabel: '隐藏用户组',
    deleteGroupLabel: '删除用户组',
    deletingGroupLabel: '删除中...',
    deleteGroupBlockedText: '系统默认用户组不允许删除',
    cancelLabel: '取消',
    saveGroupLabel: '保存',
    savingGroupLabel: '保存中...',
    unknownModuleLabel: '未知模块',
  }),
})

registerAdminPermissionsPageConfig({
  key: 'core-permissions-page-config',
  order: 10,
  resolve: () => ({
    groupColorFallback: '#6b7c93',
    groupColorDefault: '#4d698e',
  }),
})

registerAdminPermissionsPageActionMeta({
  key: 'core-permissions-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadGroupsFailedMessage: '加载用户组失败',
    loadPermissionsFailedMessage: '加载权限失败',
    loadPermissionMetaFailedMessage: '加载权限定义失败',
    savePermissionsConfirmTitle: '保存权限配置',
    savePermissionsConfirmMessage: '权限变更会立即影响用户操作能力。确定保存当前配置吗？',
    savePermissionsConfirmText: '保存',
    savePermissionsCancelText: '取消',
    savePermissionsFailedMessage: '保存权限失败',
    groupIncompleteTitle: '信息不完整',
    groupIncompleteMessage: '请输入用户组名称',
    saveGroupFailedTitle: '保存失败',
    saveGroupFailedMessage: '未知错误',
    deleteGroupConfirmTitle: '删除用户组',
    deleteGroupConfirmMessage: name => `确定删除用户组“${name}”吗？现有成员会失去该用户组权限。`,
    deleteGroupConfirmText: '删除',
    deleteGroupCancelText: '取消',
    deleteGroupSuccessTitle: '用户组已删除',
    deleteGroupSuccessMessage: name => `用户组“${name}”已删除。`,
    deleteGroupFailedTitle: '删除失败',
    deleteGroupFailedMessage: '未知错误',
  }),
})

registerAdminUsersPageCopy({
  key: 'core-users-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '用户管理',
    pageDescription: '管理论坛用户',
    searchLabel: '搜索用户',
    searchPlaceholder: '搜索用户名或邮箱...',
    tableIdHeader: 'ID',
    tableUsernameHeader: '用户名',
    tableEmailHeader: '邮箱',
    tableDisplayNameHeader: '显示名称',
    tableDiscussionHeader: '讨论',
    tableReplyHeader: '回复',
    tableJoinedHeader: '加入时间',
    tableStatusHeader: '状态',
    tableActionHeader: '操作',
    loadingText: '加载中...',
    emptyText: '暂无用户',
    editLabel: '编辑',
    mobileEmailLabel: '邮箱',
    mobileIdLabel: 'ID',
    mobileDiscussionLabel: '讨论',
    mobileReplyLabel: '回复',
    mobileJoinedLabel: '加入时间',
    modalTitle: '编辑用户',
    usernameLabel: '用户名',
    emailLabel: '邮箱',
    displayNameLabel: '显示名称',
    bioLabel: '个人简介',
    bioPlaceholder: '管理员后台可直接维护用户简介',
    staffLabel: '管理员',
    emailConfirmedLabel: '邮箱已验证',
    groupsLabel: '用户组',
    suspendedUntilLabel: '封禁截止时间',
    suspendedUntilHelpText: '留空表示未封禁',
    suspendReasonLabel: '封禁原因',
    suspendReasonPlaceholder: '例如：垃圾广告、违规内容',
    suspendMessageLabel: '对用户显示的信息',
    suspendMessagePlaceholder: '显示给被封禁用户的提示',
    deleteLabel: '删除用户',
    deletingLabel: '删除中...',
    cancelLabel: '取消',
    saveLabel: '保存',
    savingLabel: '保存中...',
    deleteBlockedText: '当前登录管理员账号不允许删除',
    statusSuspendedLabel: '已封禁',
    statusActiveLabel: '已激活',
    statusPendingLabel: '未激活',
    riskAdminLabel: '管理员权限',
    riskGroupLabel: '用户组',
    riskSuspensionLabel: '封禁状态',
    noEmailValueText: '-',
  }),
})

registerAdminUsersPageConfig({
  key: 'core-users-page-config',
  order: 10,
  resolve: () => ({
    searchDebounceMs: 500,
    paginationLimit: 20,
    dateLocale: 'zh-CN',
    groupBadgeFallbackColor: '#7f8c8d',
    groupFallbackUnknownLabel: '?',
  }),
})

registerAdminUsersPageActionMeta({
  key: 'core-users-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadUsersFailedMessage: '加载用户失败，请稍后重试',
    loadGroupsFailedTitle: '加载用户组失败',
    loadGroupsFailedMessage: '未知错误',
    loadDetailFailedTitle: '加载用户详情失败',
    loadDetailFailedMessage: '未知错误',
    saveRiskConfirmTitle: '保存用户变更',
    saveRiskConfirmMessage: changes => `以下变更会立即影响用户权限或账号状态：${changes}。确定保存吗？`,
    saveConfirmText: '保存',
    saveCancelText: '取消',
    saveSuccessTitle: '用户已保存',
    saveSuccessMessage: '用户资料和状态已更新。',
    saveFailedTitle: '保存失败',
    saveFailedMessage: '未知错误',
    deleteConfirmTitle: '删除用户',
    deleteConfirmMessage: user => `确定删除用户“${user}”吗？该操作不可撤销。`,
    deleteConfirmText: '删除',
    deleteCancelText: '取消',
    deleteSuccessTitle: '用户已删除',
    deleteSuccessMessage: user => `用户“${user}”已删除。`,
    deleteFailedTitle: '删除失败',
    deleteFailedMessage: '未知错误',
  }),
})
