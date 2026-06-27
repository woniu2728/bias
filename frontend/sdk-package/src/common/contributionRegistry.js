import { getCurrentExtensionId } from './extensionScope.js'
import ItemList from './itemList.js'

export function upsertByKey(target, key, value) {
  const existingIndex = target.findIndex(item => item.key === key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

export function orderedRegisteredItems(target) {
  const items = new ItemList()
  target.forEach((item, index) => {
    const key = String(item?.key || item?.name || item?.type || index).trim()
    items.add(key, item, -(Number(item?.order ?? item?.priority ?? 100) || 100))
  })
  return items.toArray()
}

export function normalizeRegisteredItem(item, defaults = {}) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  const extensionId = String(item?.extensionId || item?.extension_id || getCurrentExtensionId() || '').trim()
  return {
    order: 100,
    surfaces: [],
    ...defaults,
    ...item,
    ...(moduleId ? { moduleId, module_id: moduleId } : {}),
    ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
  }
}

export function clearRegistryExtensions(targets, extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (const target of targets) {
    for (let index = target.length - 1; index >= 0; index -= 1) {
      const itemExtensionId = String(target[index]?.extensionId || target[index]?.extension_id || '').trim()
      if (!itemExtensionId) {
        continue
      }
      if (!normalizedExtensionId || itemExtensionId === normalizedExtensionId) {
        target.splice(index, 1)
      }
    }
  }
}

export function isRegisteredItemEnabled(item, context = {}) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  if (!moduleId) {
    return true
  }

  const checker = context.forumStore?.isModuleEnabled
  if (typeof checker === 'function') {
    return checker(moduleId)
  }

  return true
}

export function resolveRegisteredItem(item, context = {}) {
  if (!isRegisteredItemEnabled(item, context)) {
    return null
  }

  if (Array.isArray(item.surfaces) && item.surfaces.length > 0) {
    const currentSurface = String(context.surface || '').trim()
    if (!currentSurface || !item.surfaces.includes(currentSurface)) {
      return null
    }
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

  const getResolvedValue = field => {
    if (field in resolvedItem) {
      const value = resolvedItem[field]
      return typeof value === 'function' ? value(context) : value
    }

    const fallback = item[field]
    return typeof fallback === 'function' ? fallback(context) : fallback
  }

  return {
    ...item,
    ...resolvedItem,
    icon: getResolvedValue('icon'),
    label: getResolvedValue('label'),
    title: getResolvedValue('title'),
    tone: getResolvedValue('tone'),
    to: getResolvedValue('to'),
    href: getResolvedValue('href'),
    badge: getResolvedValue('badge'),
    count: getResolvedValue('count'),
    component: getResolvedValue('component'),
    componentProps: getResolvedValue('componentProps') || {},
    active: Boolean(
      'isActive' in resolvedItem
        ? (typeof resolvedItem.isActive === 'function' ? resolvedItem.isActive(context) : resolvedItem.active)
        : (typeof item.isActive === 'function' ? item.isActive(context) : item.active)
    ),
    description: getResolvedValue('description'),
    disabledReason: getResolvedValue('disabledReason'),
    confirm: getResolvedValue('confirm'),
    disabled: Boolean(
      'isDisabled' in resolvedItem
        ? (typeof resolvedItem.isDisabled === 'function' ? resolvedItem.isDisabled(context) : resolvedItem.disabled)
        : (typeof item.isDisabled === 'function' ? item.isDisabled(context) : item.disabled)
    ),
  }
}

export function getFirstSurfaceAwareItem(target, context = {}) {
  const resolvedItems = orderedRegisteredItems(target)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)

  if (!resolvedItems.length) {
    return null
  }

  const currentSurface = String(context.surface || '').trim()
  if (!currentSurface) {
    return resolvedItems[0]
  }

  const surfaceSpecificItem = resolvedItems.find(item => Array.isArray(item.surfaces) && item.surfaces.includes(currentSurface))
  return surfaceSpecificItem || resolvedItems[0]
}
