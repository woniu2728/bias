export {
  clearAdminRoutesForExtension,
  findAdminRouteByPath,
  getAdminDashboardActions,
  getAdminNavSections,
  getAdminRoutes,
  registerAdminRoute,
  removeAdminRoute,
} from './registry/routes.js'
import { registerAdminRoute as registerAdminRouteEntry } from './registry/routes.js'
import { createAdminRuntimeRegistry } from './runtimeRegistry.js'

export { createAdminRuntimeRegistry } from './runtimeRegistry.js'
export const adminRuntimeRegistry = createAdminRuntimeRegistry({
  registerAdminRoute: registerAdminRouteEntry,
})
export { default as AdminActionNoteModal } from './components/AdminActionNoteModal.vue'
export { default as AdminColorField } from './components/AdminColorField.vue'
export { default as AdminFilterTabs } from './components/AdminFilterTabs.vue'
export { default as AdminInlineMessage } from './components/AdminInlineMessage.vue'
export { default as AdminMultiSelectMenu } from './components/AdminMultiSelectMenu.vue'
export { default as AdminPage } from './components/AdminPage.vue'
export { default as AdminPagination } from './components/AdminPagination.vue'
export { default as AdminSelectMenu } from './components/AdminSelectMenu.vue'
export { default as AdminStateBlock } from './components/AdminStateBlock.vue'
export { default as AdminSummaryGrid } from './components/AdminSummaryGrid.vue'
export { default as AdminToolbar } from './components/AdminToolbar.vue'
export { default as ExtensionGeneratedPermissionsPage } from './views/ExtensionGeneratedPermissionsPage.vue'
export { useAdminSaveFeedback } from './composables/useAdminSaveFeedback.js'
export {
  resolveApprovalSelectionState,
  resolveApprovalTemplateOptions,
} from './composables/approvalQueueTemplates.js'
export { useModalStore } from '../stores/modal.js'
export { default as adminApi } from '../api/index.js'
export {
  getAdminDashboardAction,
  getAdminDashboardActionMeta,
  getAdminDashboardAlerts,
  getAdminDashboardConfig,
  getAdminDashboardCopy,
  getAdminDashboardQueueMetrics,
  getAdminDashboardStats,
  getAdminDashboardStatusBadges,
  getAdminDashboardStatusItems,
  getAdminDashboardStatusSummaries,
  registerAdminDashboardAction,
  registerAdminDashboardActionMeta,
  registerAdminDashboardAlert,
  registerAdminDashboardConfig,
  registerAdminDashboardCopy,
  registerAdminDashboardQueueMetric,
  registerAdminDashboardStat,
  registerAdminDashboardStatusBadge,
  registerAdminDashboardStatusItem,
  registerAdminDashboardStatusSummary,
} from './registry/dashboard.js'
export {
  getAdminAdvancedPageActionMeta,
  getAdminAdvancedPageConfig,
  getAdminAdvancedPageCopy,
  getAdminAppearancePageActionMeta,
  getAdminAppearancePageAction,
  getAdminAppearancePageActions,
  getAdminAppearancePageConfig,
  getAdminAppearancePageCopy,
  getAdminAuditLogsPageConfig,
  getAdminAuditLogsPageCopy,
  getAdminBasicsPageActionMeta,
  getAdminBasicsPageConfig,
  getAdminBasicsPageCopy,
  getAdminMailPageActionMeta,
  getAdminMailPageAction,
  getAdminMailPageActions,
  getAdminMailPageConfig,
  getAdminMailPageCopy,
  getAdminPageAction,
  getAdminPageActions,
  getAdminPageActionMeta,
  getAdminPageConfig,
  getAdminPageCopy,
  getAdminPageNoteTemplates,
  getAdminPermissionsPageActionMeta,
  getAdminPermissionsPageConfig,
  getAdminPermissionsPageCopy,
  getAdminUsersPageActionMeta,
  getAdminUsersPageConfig,
  getAdminUsersPageCopy,
  registerAdminAdvancedPageActionMeta,
  registerAdminAdvancedPageConfig,
  registerAdminAdvancedPageCopy,
  registerAdminAppearancePageActionMeta,
  registerAdminAppearancePageAction,
  registerAdminAppearancePageConfig,
  registerAdminAppearancePageCopy,
  registerAdminAuditLogsPageConfig,
  registerAdminAuditLogsPageCopy,
  registerAdminBasicsPageActionMeta,
  registerAdminBasicsPageConfig,
  registerAdminBasicsPageCopy,
  registerAdminMailPageActionMeta,
  registerAdminMailPageAction,
  registerAdminMailPageConfig,
  registerAdminMailPageCopy,
  registerAdminPageAction,
  registerAdminPageActionMeta,
  registerAdminPageConfig,
  registerAdminPageCopy,
  registerAdminPageNoteTemplate,
  registerAdminPermissionsPageActionMeta,
  registerAdminPermissionsPageConfig,
  registerAdminPermissionsPageCopy,
  registerAdminUsersPageActionMeta,
  registerAdminUsersPageConfig,
  registerAdminUsersPageCopy,
} from './registry/pages.js'
export {
  getAdminPermissionScopes,
  registerAdminPermissionScope,
} from './registry/permissionScopes.js'

import './registry/bootstrap/routes.js'
import './registry/bootstrap/dashboard.js'
import './registry/bootstrap/basicsPage.js'
import './registry/bootstrap/appearancePage.js'
import './registry/bootstrap/mailPage.js'
import './registry/bootstrap/advancedPage.js'
import './registry/bootstrap/auditLogsPage.js'
import './registry/bootstrap/permissionsPage.js'

export const forContext = context => adminRuntimeRegistry.for(context)
export { forContext as for }
export const registerSetting = (setting, priority) => adminRuntimeRegistry.registerSetting(setting, priority)
export const registerCustomSetting = (setting, priority) => adminRuntimeRegistry.registerCustomSetting(setting, priority)
export const setSetting = (setting, replacement) => adminRuntimeRegistry.setSetting(setting, replacement)
export const setSettingPriority = (setting, priority) => adminRuntimeRegistry.setSettingPriority(setting, priority)
export const removeSetting = setting => adminRuntimeRegistry.removeSetting(setting)
export const getSettings = context => adminRuntimeRegistry.getSettings(context)
export const registerPermission = (permission, type, priority) => adminRuntimeRegistry.registerPermission(permission, type, priority)
export const setPermission = (permission, replacement, type) => adminRuntimeRegistry.setPermission(permission, replacement, type)
export const setPermissionPriority = (permission, type, priority) => adminRuntimeRegistry.setPermissionPriority(permission, type, priority)
export const removePermission = (permission, type) => adminRuntimeRegistry.removePermission(permission, type)
export const getPermissions = (context, type) => adminRuntimeRegistry.getPermissions(context, type)
export const registerPage = page => adminRuntimeRegistry.registerPage(page)
export const getPages = context => adminRuntimeRegistry.getPages(context)
export const generalIndex = adminRuntimeRegistry.generalIndex
