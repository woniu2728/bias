import ItemList from '../common/itemList.js'

export function createAdminRuntimeRegistry(base = {}) {
  const settings = new Map()
  const permissions = new Map()
  const pages = []
  const generalIndexState = new Map()
  let activeContext = ''
  let activeGeneralIndexContext = ''

  const registry = {
    ...base,
    for(context = '') {
      activeContext = normalizeContext(context)
      return registry
    },
    registerSetting(setting, priority = 0, key = null) {
      const normalized = normalizeSettingConfig(setting, key)
      if (!normalized) return null
      const definition = withRuntimeConfig(normalized, {
        priority: Number(priority) || 0,
        custom: false,
      })
      return upsertScoped(settings, activeContext, definition.key || definition.setting, definition)
    },
    registerCustomSetting(setting, priority = 0) {
      const normalized = normalizeConfig(setting, 'key')
      if (!normalized) return null
      return upsertScoped(settings, activeContext, normalized.key, {
        priority: Number(priority) || 0,
        custom: true,
        ...normalized,
      })
    },
    setSetting(key, replacement) {
      return replaceScoped(settings, activeContext, key, replacement)
    },
    setSettingPriority(key, priority = 0) {
      return updateScoped(settings, activeContext, key, item => ({
        ...item,
        priority: Number(priority) || 0,
      }), { priority })
    },
    removeSetting(key) {
      return removeScoped(settings, activeContext, key)
    },
    getSettings(context = activeContext) {
      return getScoped(settings, context)
    },
    getExtensionSettings(context = activeContext) {
      return getScopedItemList(settings, context)
    },
    registerPermission(permission, type = 'moderate', priority = 0) {
      const normalized = normalizeConfig(permission, 'permission')
      if (!normalized) return null
      return upsertScoped(permissions, permissionContext(activeContext, type), normalized.permission, {
        priority: Number(priority) || 0,
        type: normalizeContext(type) || 'moderate',
        ...normalized,
      })
    },
    setPermission(permission, replacement, type = 'moderate') {
      return replaceScoped(permissions, permissionContext(activeContext, type), permission, replacement)
    },
    setPermissionPriority(permission, type = 'moderate', priority = 0) {
      return updateScoped(permissions, permissionContext(activeContext, type), permission, item => ({
        ...item,
        priority: Number(priority) || 0,
      }), { priority })
    },
    removePermission(permission, type = 'moderate') {
      return removeScoped(permissions, permissionContext(activeContext, type), permission)
    },
    getPermissions(context = activeContext, type = '') {
      if (type) {
        return getScoped(permissions, permissionContext(context, type))
      }
      const prefix = `${normalizeContext(context)}:`
      return [...permissions.entries()]
        .filter(([key]) => key.startsWith(prefix))
        .reduce((merged, [, items]) => merged.merge(items), new ItemList())
        .toArray()
    },
    getAllPermissions(type = 'moderate') {
      const normalizedType = normalizeContext(type) || 'moderate'
      return [...permissions.entries()]
        .filter(([key]) => key.endsWith(`:${normalizedType}`))
        .reduce((merged, [, items]) => merged.merge(items), new ItemList())
    },
    getExtensionPermissions(context = activeContext, type = 'moderate') {
      return getScopedItemList(permissions, permissionContext(context, type))
    },
    registerPage(page) {
      if (!page || typeof page !== 'object') return null
      const normalized = {
        extensionId: activeContext,
        extension_id: activeContext,
        ...page,
      }
      const key = normalized.name || normalized.path
      const index = pages.findIndex(item => (item.name || item.path) === key)
      if (index >= 0) {
        pages.splice(index, 1, normalized)
      } else {
        pages.push(normalized)
      }
      if (typeof base.registerAdminRoute === 'function') {
        base.registerAdminRoute(normalized)
      }
      return normalized
    },
    getPages(context = '') {
      const normalized = normalizeContext(context)
      return pages
        .filter(item => !normalized || item.extensionId === normalized || item.extension_id === normalized)
        .sort((left, right) => (left.navOrder || left.order || 100) - (right.navOrder || right.order || 100))
    },
    generalIndex: {
      for(context = '') {
        activeGeneralIndexContext = normalizeContext(context)
        return registry.generalIndex
      },
      add(type, items) {
        const normalizedType = normalizeContext(type)
        if (!normalizedType) return []
        const values = Array.isArray(items) ? items : [items].filter(Boolean)
        const key = `${activeGeneralIndexContext}:${normalizedType}`
        const collection = generalIndexState.get(key) || []
        collection.push(...values)
        generalIndexState.set(key, collection)
        return values
      },
      get(context = activeGeneralIndexContext, type = '') {
        const normalized = normalizeContext(context)
        const normalizedType = normalizeContext(type)
        return [...generalIndexState.entries()]
          .filter(([key]) => {
            if (normalizedType) return key === `${normalized}:${normalizedType}`
            return key.startsWith(`${normalized}:`)
          })
          .flatMap(([, items]) => items)
      },
    },
  }

  return registry
}

export const adminRuntimeRegistry = createAdminRuntimeRegistry()

function normalizeConfig(value, keyField) {
  if (!value || typeof value !== 'object') return null
  const key = normalizeContext(value[keyField] || value.key || value.permission || value.id)
  if (!key) return null
  return {
    ...value,
    [keyField]: key,
  }
}

function normalizeSettingConfig(value, key = null) {
  if (typeof value === 'function') {
    const settingKey = normalizeContext(key || value.setting || value.key || Math.random().toString(36).slice(2))
    value.setting = settingKey
    value.key = settingKey
    return value
  }
  return normalizeConfig(value, 'key')
}

function withRuntimeConfig(value, config) {
  if (typeof value === 'function') {
    Object.assign(value, config)
    return value
  }
  return {
    ...config,
    ...value,
  }
}

function normalizeContext(value) {
  return String(value || '').trim()
}

function scopedItems(store, context) {
  const key = normalizeContext(context)
  if (!store.has(key)) {
    store.set(key, new ItemList())
  }
  return store.get(key)
}

function upsertScoped(store, context, key, item) {
  const items = scopedItems(store, context)
  items.add(normalizeContext(key), item, Number(item.priority) || 0)
  return item
}

function replaceScoped(store, context, key, replacement) {
  if (typeof replacement !== 'function') return null
  return updateScoped(store, context, key, item => replacement(item))
}

function updateScoped(store, context, key, callback, { priority = null } = {}) {
  const items = scopedItems(store, context)
  const normalizedKey = normalizeContext(key)
  if (!items.has(normalizedKey)) return null
  const updated = callback(items.get(normalizedKey))
  if (!updated) {
    items.remove(normalizedKey)
    return null
  }
  items.setContent(normalizedKey, updated)
  if (priority !== null) {
    items.setPriority(normalizedKey, Number(priority) || 0)
  } else if (updated.priority !== undefined) {
    items.setPriority(normalizedKey, Number(updated.priority) || 0)
  }
  return updated
}

function removeScoped(store, context, key) {
  const items = scopedItems(store, context)
  const normalizedKey = normalizeContext(key)
  if (!items.has(normalizedKey)) return false
  items.remove(normalizedKey)
  return true
}

function getScoped(store, context) {
  return scopedItems(store, context).toArray()
}

function getScopedItemList(store, context) {
  const list = new ItemList()
  list.merge(scopedItems(store, context))
  return list
}

function permissionContext(context, type) {
  return `${normalizeContext(context)}:${normalizeContext(type) || 'moderate'}`
}
