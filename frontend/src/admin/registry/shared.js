import { getCurrentExtensionId } from '../../common/extensionRuntime.js'

const registryTargets = []

function upsertByKey(target, value) {
  const existingIndex = target.findIndex(item => item.key === value.key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function resolveAdminItem(item, context = {}) {
  if (!isAdminItemEnabled(item, context)) {
    return null
  }

  const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
  if (!isVisible) {
    return null
  }

  const resolvedItem = typeof item.resolve === 'function'
    ? item.resolve(context)
    : item

  if (!resolvedItem) {
    return null
  }

  return {
    ...item,
    ...resolvedItem,
  }
}

function sortByOrder(left, right) {
  return (left.order || 100) - (right.order || 100)
}

function normalizeAdminItem(item, defaults = {}) {
  const extensionId = String(item?.extensionId || item?.extension_id || getCurrentExtensionId() || '').trim()
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  return {
    order: 100,
    ...defaults,
    ...item,
    ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
    ...(moduleId ? { moduleId, module_id: moduleId } : {}),
  }
}

function isAdminItemEnabled(item, context = {}) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  if (!moduleId) {
    return true
  }

  const checker = context.isModuleEnabled
  if (typeof checker === 'function') {
    return checker(moduleId)
  }

  return true
}

function clearItemsForExtension(items, extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const itemExtensionId = String(items[index]?.extensionId || items[index]?.extension_id || '').trim()
    if (!itemExtensionId) {
      continue
    }
    if (!normalizedExtensionId || itemExtensionId === normalizedExtensionId) {
      items.splice(index, 1)
    }
  }
}

export function clearAdminRegistryExtensions(extensionId = '') {
  for (const items of registryTargets) {
    clearItemsForExtension(items, extensionId)
  }
}

export function createSingleItemRegistry(defaults = {}) {
  const items = []
  registryTargets.push(items)

  return {
    register(item) {
      return upsertByKey(items, normalizeAdminItem(item, defaults))
    },
    get(context = {}) {
      return [...items]
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .find(Boolean) || null
    },
    clear(extensionId = '') {
      clearItemsForExtension(items, extensionId)
    },
  }
}

export function createListItemRegistry(defaults = {}) {
  const items = []
  registryTargets.push(items)

  return {
    register(item) {
      return upsertByKey(items, normalizeAdminItem(item, defaults))
    },
    get(context = {}) {
      return [...items]
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .filter(Boolean)
    },
    getByKey(context = {}, key = '') {
      if (!key) {
        return null
      }

      return [...items]
        .filter(item => item.key === key)
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .find(Boolean) || null
    },
    clear(extensionId = '') {
      clearItemsForExtension(items, extensionId)
    },
  }
}
