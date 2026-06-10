import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

const notificationRenderers = getFrontendRegistrySlot('notifications.renderers')
const registryTargets = [notificationRenderers]

export function clearNotificationRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
}

export function registerNotificationRenderer(item) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  const navigationScope = String(item?.navigationScope || item?.navigation_scope || '').trim()
  const normalizedItem = normalizeRegisteredItem({
    icon: 'fas fa-bell',
    navigationTarget: null,
    navigationScope: 'notifications',
    unreadCountField: '',
    ...item,
    key: item?.key || item?.type,
    type: item?.type || item?.key,
  })
  if (moduleId) {
    normalizedItem.moduleId = moduleId
    normalizedItem.module_id = moduleId
  }
  if (navigationScope) {
    normalizedItem.navigationScope = navigationScope
    normalizedItem.navigation_scope = navigationScope
  }
  return upsertByKey(notificationRenderers, normalizedItem.key, normalizedItem)
}

export function getNotificationRenderers(context = {}) {
  return orderedRegisteredItems(notificationRenderers)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerNotificationType(type, component, options = {}) {
  const normalizedType = String(type || '').trim()
  if (!normalizedType) {
    return null
  }

  return registerNotificationRenderer({
    ...options,
    key: options.key || normalizedType,
    type: normalizedType,
    component,
  })
}

export function getNotificationComponent(type) {
  const normalizedType = String(type || '').trim()
  if (!normalizedType) {
    return null
  }

  return getNotificationRenderers()
    .find(item => item.type === normalizedType || item.key === normalizedType)
    ?.component || null
}

export function getNotificationNavigationTarget(type, notification = null) {
  const normalizedType = String(type || '').trim()
  if (!normalizedType) {
    return null
  }

  const renderer = getNotificationRenderers()
    .find(item => item.type === normalizedType || item.key === normalizedType)
  if (!renderer) {
    return null
  }

  if (typeof renderer.navigationTarget === 'function') {
    return renderer.navigationTarget(notification)
  }

  return renderer.navigationTarget || null
}
