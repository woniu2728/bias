import { createSingleItemRegistry } from './shared.js'


function createPageActionMetaRegistry() {
  return createSingleItemRegistry()
}


const modulesPageActionMeta = createPageActionMetaRegistry()
const basicsPageActionMeta = createPageActionMetaRegistry()
const appearancePageActionMeta = createPageActionMetaRegistry()
const mailPageActionMeta = createPageActionMetaRegistry()
const advancedPageActionMeta = createPageActionMetaRegistry()
const approvalQueuePageActionMeta = createPageActionMetaRegistry()
const flagsPageActionMeta = createPageActionMetaRegistry()
const permissionsPageActionMeta = createPageActionMetaRegistry()
const usersPageActionMeta = createPageActionMetaRegistry()
const tagsPageActionMeta = createPageActionMetaRegistry()

export const registerAdminModulesPageActionMeta = modulesPageActionMeta.register
export const getAdminModulesPageActionMeta = modulesPageActionMeta.get

export const registerAdminBasicsPageActionMeta = basicsPageActionMeta.register
export const getAdminBasicsPageActionMeta = basicsPageActionMeta.get

export const registerAdminAppearancePageActionMeta = appearancePageActionMeta.register
export const getAdminAppearancePageActionMeta = appearancePageActionMeta.get

export const registerAdminMailPageActionMeta = mailPageActionMeta.register
export const getAdminMailPageActionMeta = mailPageActionMeta.get

export const registerAdminAdvancedPageActionMeta = advancedPageActionMeta.register
export const getAdminAdvancedPageActionMeta = advancedPageActionMeta.get

export const registerAdminApprovalQueuePageActionMeta = approvalQueuePageActionMeta.register
export const getAdminApprovalQueuePageActionMeta = approvalQueuePageActionMeta.get

export const registerAdminFlagsPageActionMeta = flagsPageActionMeta.register
export const getAdminFlagsPageActionMeta = flagsPageActionMeta.get

export const registerAdminPermissionsPageActionMeta = permissionsPageActionMeta.register
export const getAdminPermissionsPageActionMeta = permissionsPageActionMeta.get

export const registerAdminUsersPageActionMeta = usersPageActionMeta.register
export const getAdminUsersPageActionMeta = usersPageActionMeta.get

export const registerAdminTagsPageActionMeta = tagsPageActionMeta.register
export const getAdminTagsPageActionMeta = tagsPageActionMeta.get
