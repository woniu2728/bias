import { createSingleItemRegistry } from './shared.js'


const pageCopyRegistries = new Map()

function getPageCopyRegistry(pageKey = '') {
  const normalizedPageKey = String(pageKey || '').trim()
  if (!normalizedPageKey) {
    throw new Error('admin page copy registry requires a page key')
  }

  if (!pageCopyRegistries.has(normalizedPageKey)) {
    pageCopyRegistries.set(normalizedPageKey, createSingleItemRegistry())
  }

  return pageCopyRegistries.get(normalizedPageKey)
}

export function registerAdminPageCopy(pageKey, item) {
  return getPageCopyRegistry(pageKey).register(item)
}

export function getAdminPageCopy(pageKey, context = {}) {
  return getPageCopyRegistry(pageKey).get(context)
}

const basicsPageCopy = getPageCopyRegistry('core.basics')
const appearancePageCopy = getPageCopyRegistry('core.appearance')
const mailPageCopy = getPageCopyRegistry('core.mail')
const advancedPageCopy = getPageCopyRegistry('core.advanced')
const permissionsPageCopy = getPageCopyRegistry('core.permissions')
const usersPageCopy = getPageCopyRegistry('core.users')
const auditLogsPageCopy = getPageCopyRegistry('core.audit-logs')

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

export const registerAdminPermissionsPageCopy = permissionsPageCopy.register
export const getAdminPermissionsPageCopy = permissionsPageCopy.get

export const registerAdminUsersPageCopy = usersPageCopy.register
export const getAdminUsersPageCopy = usersPageCopy.get
