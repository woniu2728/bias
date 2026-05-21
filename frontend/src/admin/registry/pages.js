import { createListItemRegistry, createSingleItemRegistry } from './shared.js'


function createPageSectionRegistries() {
  return {
    copy: createSingleItemRegistry(),
    config: createSingleItemRegistry(),
    actionMeta: createSingleItemRegistry(),
  }
}


const modulesPage = createPageSectionRegistries()
const basicsPage = createPageSectionRegistries()
const appearancePage = createPageSectionRegistries()
const mailPage = createPageSectionRegistries()
const advancedPage = createPageSectionRegistries()
const approvalQueuePage = createPageSectionRegistries()
const flagsPage = createPageSectionRegistries()
const permissionsPage = createPageSectionRegistries()
const usersPage = createPageSectionRegistries()
const tagsPage = createPageSectionRegistries()
const auditLogsPageCopy = createSingleItemRegistry()
const auditLogsPageConfig = createSingleItemRegistry()
const approvalQueueNoteTemplates = createListItemRegistry()

export const registerAdminModulesPageCopy = modulesPage.copy.register
export const getAdminModulesPageCopy = modulesPage.copy.get
export const registerAdminModulesPageConfig = modulesPage.config.register
export const getAdminModulesPageConfig = modulesPage.config.get
export const registerAdminModulesPageActionMeta = modulesPage.actionMeta.register
export const getAdminModulesPageActionMeta = modulesPage.actionMeta.get

export const registerAdminBasicsPageCopy = basicsPage.copy.register
export const getAdminBasicsPageCopy = basicsPage.copy.get
export const registerAdminBasicsPageConfig = basicsPage.config.register
export const getAdminBasicsPageConfig = basicsPage.config.get
export const registerAdminBasicsPageActionMeta = basicsPage.actionMeta.register
export const getAdminBasicsPageActionMeta = basicsPage.actionMeta.get

export const registerAdminAppearancePageCopy = appearancePage.copy.register
export const getAdminAppearancePageCopy = appearancePage.copy.get
export const registerAdminAppearancePageConfig = appearancePage.config.register
export const getAdminAppearancePageConfig = appearancePage.config.get
export const registerAdminAppearancePageActionMeta = appearancePage.actionMeta.register
export const getAdminAppearancePageActionMeta = appearancePage.actionMeta.get

export const registerAdminMailPageCopy = mailPage.copy.register
export const getAdminMailPageCopy = mailPage.copy.get
export const registerAdminMailPageConfig = mailPage.config.register
export const getAdminMailPageConfig = mailPage.config.get
export const registerAdminMailPageActionMeta = mailPage.actionMeta.register
export const getAdminMailPageActionMeta = mailPage.actionMeta.get

export const registerAdminAdvancedPageCopy = advancedPage.copy.register
export const getAdminAdvancedPageCopy = advancedPage.copy.get
export const registerAdminAdvancedPageConfig = advancedPage.config.register
export const getAdminAdvancedPageConfig = advancedPage.config.get
export const registerAdminAdvancedPageActionMeta = advancedPage.actionMeta.register
export const getAdminAdvancedPageActionMeta = advancedPage.actionMeta.get

export const registerAdminAuditLogsPageCopy = auditLogsPageCopy.register
export const getAdminAuditLogsPageCopy = auditLogsPageCopy.get
export const registerAdminAuditLogsPageConfig = auditLogsPageConfig.register
export const getAdminAuditLogsPageConfig = auditLogsPageConfig.get

export const registerAdminApprovalQueuePageCopy = approvalQueuePage.copy.register
export const getAdminApprovalQueuePageCopy = approvalQueuePage.copy.get
export const registerAdminApprovalQueuePageConfig = approvalQueuePage.config.register
export function getAdminApprovalQueuePageConfig(context = {}) {
  const config = approvalQueuePage.config.get(context)
  if (!config) {
    return null
  }

  return {
    ...config,
    noteTemplates: getAdminApprovalQueueNoteTemplates(context),
  }
}
export const registerAdminApprovalQueuePageActionMeta = approvalQueuePage.actionMeta.register
export const getAdminApprovalQueuePageActionMeta = approvalQueuePage.actionMeta.get
export const registerAdminApprovalQueueNoteTemplate = approvalQueueNoteTemplates.register
export const getAdminApprovalQueueNoteTemplates = approvalQueueNoteTemplates.get

export const registerAdminFlagsPageCopy = flagsPage.copy.register
export const getAdminFlagsPageCopy = flagsPage.copy.get
export const registerAdminFlagsPageConfig = flagsPage.config.register
export const getAdminFlagsPageConfig = flagsPage.config.get
export const registerAdminFlagsPageActionMeta = flagsPage.actionMeta.register
export const getAdminFlagsPageActionMeta = flagsPage.actionMeta.get

export const registerAdminPermissionsPageCopy = permissionsPage.copy.register
export const getAdminPermissionsPageCopy = permissionsPage.copy.get
export const registerAdminPermissionsPageConfig = permissionsPage.config.register
export const getAdminPermissionsPageConfig = permissionsPage.config.get
export const registerAdminPermissionsPageActionMeta = permissionsPage.actionMeta.register
export const getAdminPermissionsPageActionMeta = permissionsPage.actionMeta.get

export const registerAdminUsersPageCopy = usersPage.copy.register
export const getAdminUsersPageCopy = usersPage.copy.get
export const registerAdminUsersPageConfig = usersPage.config.register
export const getAdminUsersPageConfig = usersPage.config.get
export const registerAdminUsersPageActionMeta = usersPage.actionMeta.register
export const getAdminUsersPageActionMeta = usersPage.actionMeta.get

export const registerAdminTagsPageConfig = tagsPage.config.register
export const getAdminTagsPageConfig = tagsPage.config.get
export const registerAdminTagsPageCopy = tagsPage.copy.register
export const getAdminTagsPageCopy = tagsPage.copy.get
export const registerAdminTagsPageActionMeta = tagsPage.actionMeta.register
export const getAdminTagsPageActionMeta = tagsPage.actionMeta.get
