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
    registerSetting(setting, priority = 0) {
      const normalized = normalizeConfig(setting, 'key')
      if (!normalized) return null
      return upsertScoped(settings, activeContext, {
        priority: Number(priority) || 0,
        custom: false,
        ...normalized,
      }, 'key')
    },
    registerCustomSetting(setting, priority = 0) {
      const normalized = normalizeConfig(setting, 'key')
      if (!normalized) return null
      return upsertScoped(settings, activeContext, {
        priority: Number(priority) || 0,
        custom: true,
        ...normalized,
      }, 'key')
    },
    setSetting(key, replacement) {
      return replaceScoped(settings, activeContext, key, 'key', replacement)
    },
    setSettingPriority(key, priority = 0) {
      return updateScoped(settings, activeContext, key, 'key', item => ({
        ...item,
        priority: Number(priority) || 0,
      }))
    },
    removeSetting(key) {
      return removeScoped(settings, activeContext, key, 'key')
    },
    getSettings(context = activeContext) {
      return getScoped(settings, context)
    },
    registerPermission(permission, type = 'moderate', priority = 0) {
      const normalized = normalizeConfig(permission, 'permission')
      if (!normalized) return null
      return upsertScoped(permissions, permissionContext(activeContext, type), {
        priority: Number(priority) || 0,
        type: normalizeContext(type) || 'moderate',
        ...normalized,
      }, 'permission')
    },
    setPermission(permission, replacement, type = 'moderate') {
      return replaceScoped(permissions, permissionContext(activeContext, type), permission, 'permission', replacement)
    },
    setPermissionPriority(permission, type = 'moderate', priority = 0) {
      return updateScoped(permissions, permissionContext(activeContext, type), permission, 'permission', item => ({
        ...item,
        priority: Number(priority) || 0,
      }))
    },
    removePermission(permission, type = 'moderate') {
      return removeScoped(permissions, permissionContext(activeContext, type), permission, 'permission')
    },
    getPermissions(context = activeContext, type = '') {
      if (type) {
        return getScoped(permissions, permissionContext(context, type))
      }
      const prefix = `${normalizeContext(context)}:`
      return [...permissions.entries()]
        .filter(([key]) => key.startsWith(prefix))
        .flatMap(([, items]) => items)
        .sort(sortByPriority)
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
  const key = normalizeContext(value[keyField] || value.key || value.permission)
  if (!key) return null
  return {
    ...value,
    [keyField]: key,
  }
}

function normalizeContext(value) {
  return String(value || '').trim()
}

function scopedItems(store, context) {
  const key = normalizeContext(context)
  if (!store.has(key)) {
    store.set(key, [])
  }
  return store.get(key)
}

function upsertScoped(store, context, item, keyField) {
  const items = scopedItems(store, context)
  const index = items.findIndex(candidate => candidate[keyField] === item[keyField])
  if (index >= 0) {
    items.splice(index, 1, item)
  } else {
    items.push(item)
  }
  return item
}

function replaceScoped(store, context, key, keyField, replacement) {
  if (typeof replacement !== 'function') return null
  return updateScoped(store, context, key, keyField, item => replacement(item))
}

function updateScoped(store, context, key, keyField, callback) {
  const items = scopedItems(store, context)
  const normalizedKey = normalizeContext(key)
  const index = items.findIndex(item => item[keyField] === normalizedKey)
  if (index < 0) return null
  const updated = callback(items[index])
  if (!updated) {
    items.splice(index, 1)
    return null
  }
  items.splice(index, 1, updated)
  return updated
}

function removeScoped(store, context, key, keyField) {
  const items = scopedItems(store, context)
  const normalizedKey = normalizeContext(key)
  const index = items.findIndex(item => item[keyField] === normalizedKey)
  if (index < 0) return false
  items.splice(index, 1)
  return true
}

function getScoped(store, context) {
  return [...scopedItems(store, context)].sort(sortByPriority)
}

function permissionContext(context, type) {
  return `${normalizeContext(context)}:${normalizeContext(type) || 'moderate'}`
}

function sortByPriority(left, right) {
  return (left.priority || 0) - (right.priority || 0)
}
