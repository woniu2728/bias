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
  return mergePageContributions(getPageCopyRegistry(pageKey).getAll(context))
}

function mergePageContributions(items) {
  if (!Array.isArray(items) || !items.length) {
    return null
  }

  return [...items].reverse().reduce((merged, item) => {
    const next = { ...merged }
    for (const [key, value] of Object.entries(item || {})) {
      next[key] = value
    }
    return next
  }, {})
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
export const getAdminAppearancePageCopy = context => getAdminPageCopy('core.appearance', context)

export const registerAdminMailPageCopy = mailPageCopy.register
export const getAdminMailPageCopy = context => getAdminPageCopy('core.mail', context)

export const registerAdminAdvancedPageCopy = advancedPageCopy.register
export const getAdminAdvancedPageCopy = context => getAdminPageCopy('core.advanced', context)

export const registerAdminAuditLogsPageCopy = auditLogsPageCopy.register
export const getAdminAuditLogsPageCopy = auditLogsPageCopy.get

export const registerAdminPermissionsPageCopy = permissionsPageCopy.register
export const getAdminPermissionsPageCopy = permissionsPageCopy.get

export const registerAdminUsersPageCopy = usersPageCopy.register
export const getAdminUsersPageCopy = usersPageCopy.get
