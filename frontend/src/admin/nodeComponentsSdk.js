import api from '../api/index.js'

export const adminApi = api

export const AdminActionNoteModal = null
export const AdminColorField = null
export const AdminFilterTabs = null
export const AdminInlineMessage = null
export const AdminMultiSelectMenu = null
export const AdminPage = null
export const AdminPagination = null
export const AdminSelectMenu = null
export const AdminStateBlock = null
export const AdminSummaryGrid = null
export const AdminToolbar = null
export const ExtensionGeneratedPermissionsPage = null

export {
  getAdminPageActionMeta,
  getAdminPageConfig,
  getAdminPageCopy,
  getAdminUsersPageActionMeta,
  getAdminUsersPageConfig,
  getAdminUsersPageCopy,
} from './registry/pages.js'
export {
  resolveApprovalSelectionState,
  resolveApprovalTemplateOptions,
} from './composables/approvalQueueTemplates.js'
export { useAdminSaveFeedback } from './composables/useAdminSaveFeedback.js'
export { useModalStore } from '../stores/modal.js'
