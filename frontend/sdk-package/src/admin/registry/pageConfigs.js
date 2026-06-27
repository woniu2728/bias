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
  const config = getMergedAdminPageConfig(pageKey, context)
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

export function getMergedAdminPageConfig(pageKey, context = {}) {
  return mergePageContributions(getPageConfigRegistry(pageKey).getAll(context))
}

function mergePageContributions(items) {
  if (!Array.isArray(items) || !items.length) {
    return null
  }

  return [...items].reverse().reduce((merged, item) => deepMerge(merged, item), {})
}

function deepMerge(target, source) {
  if (!isPlainObject(target)) {
    return cloneMergeValue(source)
  }
  if (!isPlainObject(source)) {
    return cloneMergeValue(source)
  }

  const merged = { ...target }
  for (const [key, value] of Object.entries(source)) {
    if (isPlainObject(value) && isPlainObject(merged[key])) {
      merged[key] = deepMerge(merged[key], value)
    } else if (Array.isArray(value) && Array.isArray(merged[key])) {
      merged[key] = [...merged[key], ...value]
    } else {
      merged[key] = cloneMergeValue(value)
    }
  }
  return merged
}

function cloneMergeValue(value) {
  if (Array.isArray(value)) {
    return [...value]
  }
  if (isPlainObject(value)) {
    return deepMerge({}, value)
  }
  return value
}

function isPlainObject(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
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
export const getAdminAppearancePageConfig = context => getMergedAdminPageConfig('core.appearance', context)

export const registerAdminMailPageConfig = mailPageConfig.register
export const getAdminMailPageConfig = context => getMergedAdminPageConfig('core.mail', context)

export const registerAdminAdvancedPageConfig = advancedPageConfig.register
export const getAdminAdvancedPageConfig = context => getMergedAdminPageConfig('core.advanced', context)

export const registerAdminAuditLogsPageConfig = auditLogsPageConfig.register
export const getAdminAuditLogsPageConfig = auditLogsPageConfig.get

export const registerAdminPermissionsPageConfig = permissionsPageConfig.register
export const getAdminPermissionsPageConfig = permissionsPageConfig.get

export const registerAdminUsersPageConfig = usersPageConfig.register
export const getAdminUsersPageConfig = usersPageConfig.get
