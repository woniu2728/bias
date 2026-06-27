import { createListItemRegistry } from './shared.js'


const pageActionRegistries = new Map()

function getPageActionRegistry(pageKey = '') {
  const normalizedPageKey = String(pageKey || '').trim()
  if (!normalizedPageKey) {
    throw new Error('admin page action registry requires a page key')
  }

  if (!pageActionRegistries.has(normalizedPageKey)) {
    pageActionRegistries.set(normalizedPageKey, createListItemRegistry())
  }

  return pageActionRegistries.get(normalizedPageKey)
}

export function registerAdminPageAction(pageKey, item) {
  return getPageActionRegistry(pageKey).register(item)
}

export function getAdminPageActions(pageKey, context = {}) {
  return getPageActionRegistry(pageKey).get(context)
}

export function getAdminPageAction(pageKey, key = '', context = {}) {
  return getPageActionRegistry(pageKey).getByKey(context, key)
}

const appearancePageActions = getPageActionRegistry('core.appearance')
const mailPageActions = getPageActionRegistry('core.mail')

export const registerAdminAppearancePageAction = appearancePageActions.register
export const getAdminAppearancePageActions = appearancePageActions.get
export const getAdminAppearancePageAction = (key, context = {}) => getAdminPageAction('core.appearance', key, context)

export const registerAdminMailPageAction = mailPageActions.register
export const getAdminMailPageActions = mailPageActions.get
export const getAdminMailPageAction = (key, context = {}) => getAdminPageAction('core.mail', key, context)
