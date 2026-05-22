import { createSingleItemRegistry } from './shared.js'


function createPageCopyRegistry() {
  return createSingleItemRegistry()
}


const modulesPageCopy = createPageCopyRegistry()
const basicsPageCopy = createPageCopyRegistry()
const appearancePageCopy = createPageCopyRegistry()
const mailPageCopy = createPageCopyRegistry()
const advancedPageCopy = createPageCopyRegistry()
const approvalQueuePageCopy = createPageCopyRegistry()
const flagsPageCopy = createPageCopyRegistry()
const permissionsPageCopy = createPageCopyRegistry()
const usersPageCopy = createPageCopyRegistry()
const tagsPageCopy = createPageCopyRegistry()
const auditLogsPageCopy = createPageCopyRegistry()

export const registerAdminModulesPageCopy = modulesPageCopy.register
export const getAdminModulesPageCopy = modulesPageCopy.get

export const registerAdminBasicsPageCopy = basicsPageCopy.register
export const getAdminBasicsPageCopy = basicsPageCopy.get

export const registerAdminAppearancePageCopy = appearancePageCopy.register
export const getAdminAppearancePageCopy = appearancePageCopy.get

export const registerAdminMailPageCopy = mailPageCopy.register
export const getAdminMailPageCopy = mailPageCopy.get

export const registerAdminAdvancedPageCopy = advancedPageCopy.register
export const getAdminAdvancedPageCopy = advancedPageCopy.get

export const registerAdminAuditLogsPageCopy = auditLogsPageCopy.register
export const getAdminAuditLogsPageCopy = auditLogsPageCopy.get

export const registerAdminApprovalQueuePageCopy = approvalQueuePageCopy.register
export const getAdminApprovalQueuePageCopy = approvalQueuePageCopy.get

export const registerAdminFlagsPageCopy = flagsPageCopy.register
export const getAdminFlagsPageCopy = flagsPageCopy.get

export const registerAdminPermissionsPageCopy = permissionsPageCopy.register
export const getAdminPermissionsPageCopy = permissionsPageCopy.get

export const registerAdminUsersPageCopy = usersPageCopy.register
export const getAdminUsersPageCopy = usersPageCopy.get

export const registerAdminTagsPageCopy = tagsPageCopy.register
export const getAdminTagsPageCopy = tagsPageCopy.get
