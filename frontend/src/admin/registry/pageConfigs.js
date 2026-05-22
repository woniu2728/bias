import { createSingleItemRegistry } from './shared.js'
import { getAdminApprovalQueueNoteTemplates } from './pageNoteTemplates.js'


function createPageConfigRegistry() {
  return createSingleItemRegistry()
}


const modulesPageConfig = createPageConfigRegistry()
const basicsPageConfig = createPageConfigRegistry()
const appearancePageConfig = createPageConfigRegistry()
const mailPageConfig = createPageConfigRegistry()
const advancedPageConfig = createPageConfigRegistry()
const approvalQueuePageConfig = createPageConfigRegistry()
const flagsPageConfig = createPageConfigRegistry()
const permissionsPageConfig = createPageConfigRegistry()
const usersPageConfig = createPageConfigRegistry()
const tagsPageConfig = createPageConfigRegistry()
const auditLogsPageConfig = createPageConfigRegistry()

export const registerAdminModulesPageConfig = modulesPageConfig.register
export const getAdminModulesPageConfig = modulesPageConfig.get

export const registerAdminBasicsPageConfig = basicsPageConfig.register
export const getAdminBasicsPageConfig = basicsPageConfig.get

export const registerAdminAppearancePageConfig = appearancePageConfig.register
export const getAdminAppearancePageConfig = appearancePageConfig.get

export const registerAdminMailPageConfig = mailPageConfig.register
export const getAdminMailPageConfig = mailPageConfig.get

export const registerAdminAdvancedPageConfig = advancedPageConfig.register
export const getAdminAdvancedPageConfig = advancedPageConfig.get

export const registerAdminAuditLogsPageConfig = auditLogsPageConfig.register
export const getAdminAuditLogsPageConfig = auditLogsPageConfig.get

export const registerAdminApprovalQueuePageConfig = approvalQueuePageConfig.register
export function getAdminApprovalQueuePageConfig(context = {}) {
  const config = approvalQueuePageConfig.get(context)
  if (!config) {
    return null
  }

  return {
    ...config,
    noteTemplates: getAdminApprovalQueueNoteTemplates(context),
  }
}

export const registerAdminFlagsPageConfig = flagsPageConfig.register
export const getAdminFlagsPageConfig = flagsPageConfig.get

export const registerAdminPermissionsPageConfig = permissionsPageConfig.register
export const getAdminPermissionsPageConfig = permissionsPageConfig.get

export const registerAdminUsersPageConfig = usersPageConfig.register
export const getAdminUsersPageConfig = usersPageConfig.get

export const registerAdminTagsPageConfig = tagsPageConfig.register
export const getAdminTagsPageConfig = tagsPageConfig.get
