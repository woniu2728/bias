import { createSingleItemRegistry } from './shared.js'
import { getAdminPageNoteTemplates } from './pageNoteTemplates.js'


const pageConfigRegistries = new Map()

function getPageConfigRegistry(pageKey = '') {
  const normalizedPageKey = String(pageKey || '').trim()
  if (!normalizedPageKey) {
    throw new Error('admin page config registry requires a page key')
  }

  if (!pageConfigRegistries.has(normalizedPageKey)) {
    pageConfigRegistries.set(normalizedPageKey, createSingleItemRegistry())
  }

  return pageConfigRegistries.get(normalizedPageKey)
}

export function registerAdminPageConfig(pageKey, item) {
  return getPageConfigRegistry(pageKey).register(item)
}

export function getAdminPageConfig(pageKey, context = {}) {
  const config = getPageConfigRegistry(pageKey).get(context)
  if (!config) {
    return null
  }

  const noteTemplates = getAdminPageNoteTemplates(pageKey, context)
  if (!noteTemplates.length) {
    return config
  }

  return {
    ...config,
    noteTemplates,
  }
}

const basicsPageConfig = getPageConfigRegistry('core.basics')
const appearancePageConfig = getPageConfigRegistry('core.appearance')
const mailPageConfig = getPageConfigRegistry('core.mail')
const advancedPageConfig = getPageConfigRegistry('core.advanced')
const permissionsPageConfig = getPageConfigRegistry('core.permissions')
const usersPageConfig = getPageConfigRegistry('core.users')
const auditLogsPageConfig = getPageConfigRegistry('core.audit-logs')

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

export const registerAdminPermissionsPageConfig = permissionsPageConfig.register
export const getAdminPermissionsPageConfig = permissionsPageConfig.get

export const registerAdminUsersPageConfig = usersPageConfig.register
export const getAdminUsersPageConfig = usersPageConfig.get
