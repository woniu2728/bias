import { createSingleItemRegistry } from './shared.js'


const pageActionMetaRegistries = new Map()

function getPageActionMetaRegistry(pageKey = '') {
  const normalizedPageKey = String(pageKey || '').trim()
  if (!normalizedPageKey) {
    throw new Error('admin page action meta registry requires a page key')
  }

  if (!pageActionMetaRegistries.has(normalizedPageKey)) {
    pageActionMetaRegistries.set(normalizedPageKey, createSingleItemRegistry())
  }

  return pageActionMetaRegistries.get(normalizedPageKey)
}

export function registerAdminPageActionMeta(pageKey, item) {
  return getPageActionMetaRegistry(pageKey).register(item)
}

export function getAdminPageActionMeta(pageKey, context = {}) {
  return getPageActionMetaRegistry(pageKey).get(context)
}

const basicsPageActionMeta = getPageActionMetaRegistry('core.basics')
const appearancePageActionMeta = getPageActionMetaRegistry('core.appearance')
const mailPageActionMeta = getPageActionMetaRegistry('core.mail')
const advancedPageActionMeta = getPageActionMetaRegistry('core.advanced')
const permissionsPageActionMeta = getPageActionMetaRegistry('core.permissions')
const usersPageActionMeta = getPageActionMetaRegistry('core.users')

export const registerAdminBasicsPageActionMeta = basicsPageActionMeta.register
export const getAdminBasicsPageActionMeta = basicsPageActionMeta.get

export const registerAdminAppearancePageActionMeta = appearancePageActionMeta.register
export const getAdminAppearancePageActionMeta = appearancePageActionMeta.get

export const registerAdminMailPageActionMeta = mailPageActionMeta.register
export const getAdminMailPageActionMeta = mailPageActionMeta.get

export const registerAdminAdvancedPageActionMeta = advancedPageActionMeta.register
export const getAdminAdvancedPageActionMeta = advancedPageActionMeta.get

export const registerAdminPermissionsPageActionMeta = permissionsPageActionMeta.register
export const getAdminPermissionsPageActionMeta = permissionsPageActionMeta.get

export const registerAdminUsersPageActionMeta = usersPageActionMeta.register
export const getAdminUsersPageActionMeta = usersPageActionMeta.get
