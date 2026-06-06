import { getNotificationRenderers, registerNotificationRenderer } from './frontendRegistry.js'

function normalizeType(type) {
  return String(type || '').trim()
}

function getNotificationTypeDefinition(type) {
  const normalizedType = normalizeType(type)
  if (!normalizedType) {
    return {}
  }

  return getNotificationRenderers()
    .map(item => ({
      ...item,
      type: normalizeType(item.type || item.key),
      key: item.key || item.type,
    }))
    .find(item => item.type === normalizedType) || {}
}

export function registerNotificationType(definition) {
  const normalizedType = normalizeType(definition?.type || definition?.code)
  if (!normalizedType) {
    return null
  }

  return registerNotificationRenderer({
    ...definition,
    key: definition?.key || normalizedType,
    type: normalizedType,
    navigationScope: definition?.navigation_scope || definition?.navigationScope,
  })
}

export function syncNotificationTypes(definitions = []) {
  definitions.forEach((definition, index) => {
    const normalizedType = normalizeType(definition?.code || definition?.type)
    if (!normalizedType) {
      return
    }

    const existing = getNotificationTypeDefinition(normalizedType)
    registerNotificationType({
      ...existing,
      ...definition,
      type: normalizedType,
      navigationScope: definition?.navigation_scope || definition?.navigationScope || existing?.navigationScope,
      order: Number(definition?.order ?? existing?.order ?? ((index + 1) * 10)),
    })
  })
}

export function getRegisteredNotificationTypes() {
  return getNotificationRenderers()
}
