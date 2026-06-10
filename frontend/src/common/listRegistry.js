import { getCurrentExtensionId } from './extensionRuntime.js'
import ItemList from './itemList.js'

const globalRegistryTargets = []

export function createListItemRegistry(defaults = {}) {
  const items = []
  globalRegistryTargets.push(items)
  return createRegistryAdapter(items, defaults, { single: false })
}

export function createSingleItemRegistry(defaults = {}) {
  const items = []
  globalRegistryTargets.push(items)
  return createRegistryAdapter(items, defaults, { single: true })
}

export function createExtensionRegistry() {
  const lists = new Map()
  const singles = new Map()

  const api = {
    list(name, defaults = {}) {
      const key = normalizeKey(name)
      if (!key) {
        throw new Error('Extension registry list requires a name')
      }
      if (!lists.has(key)) {
        lists.set(key, createListItemRegistry(defaults))
      }
      return lists.get(key)
    },
    single(name, defaults = {}) {
      const key = normalizeKey(name)
      if (!key) {
        throw new Error('Extension registry single requires a name')
      }
      if (!singles.has(key)) {
        singles.set(key, createSingleItemRegistry(defaults))
      }
      return singles.get(key)
    },
    add(name, item, priority) {
      return api.list(name).add(item, priority)
    },
    register(name, item, priority) {
      return api.add(name, item, priority)
    },
    replace(name, key, replacement) {
      return api.list(name).replace(key, replacement)
    },
    remove(name, key) {
      return api.list(name).remove(key)
    },
    get(name, context = {}) {
      return api.list(name).get(context)
    },
    getByKey(name, key, context = {}) {
      return api.list(name).getByKey(context, key)
    },
    getOne(name, context = {}) {
      return api.single(name).get(context)
    },
    clear(extensionId = '') {
      clearRegistryCollections([...lists.values(), ...singles.values()], extensionId)
    },
    scoped(extensionId = '') {
      return createScopedExtensionRegistry(api, extensionId)
    },
  }

  return api
}

export function clearListRegistriesForExtension(extensionId = '') {
  clearRegistryItems(globalRegistryTargets, extensionId)
}

function createScopedExtensionRegistry(registry, extensionId = '') {
  const normalizedExtensionId = normalizeKey(extensionId || getCurrentExtensionId())
  const scopedApi = {
    list: (name, defaults = {}) => {
      const target = registry.list(name, defaults)
      return createScopedRegistryAdapter(target, normalizedExtensionId)
    },
    single: (name, defaults = {}) => {
      const target = registry.single(name, defaults)
      return createScopedRegistryAdapter(target, normalizedExtensionId)
    },
    add: (name, item, priority) => scopedApi.list(name).add(item, priority),
    register: (name, item, priority) => scopedApi.add(name, item, priority),
    replace: (name, key, replacement) => registry.replace(name, key, replacement),
    remove: (name, key) => registry.remove(name, key),
    get: (name, context = {}) => registry.get(name, context),
    getByKey: (name, key, context = {}) => registry.getByKey(name, key, context),
    getOne: (name, context = {}) => registry.getOne(name, context),
    clear: () => registry.clear(normalizedExtensionId),
  }
  return scopedApi
}

function createScopedRegistryAdapter(registry, extensionId) {
  const scopedAdapter = {
    add: (item, priority) => registry.add(withExtensionId(item, extensionId), priority),
    register: (item, priority) => scopedAdapter.add(item, priority),
    set: (key, item, priority) => registry.set(key, withExtensionId(item, extensionId), priority),
    replace: (key, replacement) => registry.replace(key, replacement),
    remove: key => registry.remove(key),
    get: (context = {}) => registry.get(context),
    getByKey: (context = {}, key = '') => registry.getByKey(context, key),
    clear: () => registry.clear(extensionId),
    toItemList: (context = {}) => registry.toItemList(context),
  }
  return scopedAdapter
}

function createRegistryAdapter(items, defaults = {}, { single = false } = {}) {
  const adapter = {
    register: (item, priority) => adapter.add(item, priority),
    add(item, priority) {
      const normalized = normalizeRegisteredItem(item, defaults, priority)
      if (!normalized.key) {
        return null
      }
      return upsertByKey(items, normalized)
    },
    set(key, item, priority) {
      const normalizedKey = normalizeKey(key)
      if (!normalizedKey) {
        return null
      }
      return upsertByKey(items, normalizeRegisteredItem({ ...(item || {}), key: normalizedKey }, defaults, priority))
    },
    replace(key, replacement) {
      const normalizedKey = normalizeKey(key)
      const index = items.findIndex(item => item.key === normalizedKey)
      if (index < 0 || typeof replacement !== 'function') {
        return null
      }
      const updated = replacement(items[index])
      if (!updated) {
        items.splice(index, 1)
        return null
      }
      items.splice(index, 1, normalizeRegisteredItem({ ...updated, key: updated.key || normalizedKey }, defaults))
      return items[index]
    },
    remove(key) {
      const normalizedKey = normalizeKey(key)
      const index = items.findIndex(item => item.key === normalizedKey)
      if (index < 0) {
        return false
      }
      items.splice(index, 1)
      return true
    },
    has(key) {
      return items.some(item => item.key === normalizeKey(key))
    },
    get(context = {}) {
      const resolved = resolveRegistryItems(items, context)
      return single ? (resolved[0] || null) : resolved
    },
    getAll(context = {}) {
      return resolveRegistryItems(items, context)
    },
    getByKey(context = {}, key = '') {
      const normalizedKey = normalizeKey(key)
      if (!normalizedKey) {
        return null
      }
      return resolveRegistryItems(items.filter(item => item.key === normalizedKey), context)[0] || null
    },
    clear(extensionId = '') {
      clearItemsForExtension(items, extensionId)
    },
    raw() {
      return [...items]
    },
    toItemList(context = {}) {
      const list = new ItemList()
      for (const item of resolveRegistryItems(items, context)) {
        list.add(item.key, item, Number(item.priority ?? item.order ?? 0))
      }
      return list
    },
  }
  return adapter
}

export function normalizeRegisteredItem(item, defaults = {}, priority) {
  const value = item && typeof item === 'object' ? item : {}
  const extensionId = normalizeKey(value.extensionId || value.extension_id || getCurrentExtensionId())
  const moduleId = normalizeKey(value.moduleId || value.module_id)
  const key = normalizeKey(value.key || value.name || value.id)
  const resolvedPriority = priority !== undefined
    ? Number(priority) || 0
    : Number(value.priority ?? defaults.priority ?? 0)
  const resolvedOrder = Number(value.order ?? defaults.order ?? (resolvedPriority ? -resolvedPriority : 100))
  return {
    surfaces: [],
    ...defaults,
    ...value,
    key,
    order: resolvedOrder,
    priority: resolvedPriority,
    ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
    ...(moduleId ? { moduleId, module_id: moduleId } : {}),
  }
}

export function resolveRegistryItem(item, context = {}) {
  if (!isRegisteredItemEnabled(item, context)) {
    return null
  }
  if (!matchesSurface(item, context)) {
    return null
  }
  const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
  if (!isVisible) {
    return null
  }
  const resolved = typeof item.resolve === 'function' ? item.resolve(context) : item
  if (!resolved) {
    return null
  }
  return {
    ...item,
    ...resolved,
  }
}

export function sortRegistryItems(left, right) {
  const leftOrder = Number(left.order ?? (left.priority ? -left.priority : 100))
  const rightOrder = Number(right.order ?? (right.priority ? -right.priority : 100))
  return leftOrder - rightOrder
}

function resolveRegistryItems(items, context = {}) {
  return [...items]
    .sort(sortRegistryItems)
    .map(item => resolveRegistryItem(item, context))
    .filter(Boolean)
}

function isRegisteredItemEnabled(item, context = {}) {
  const moduleId = normalizeKey(item?.moduleId || item?.module_id)
  if (!moduleId) {
    return true
  }
  const checker = context.isModuleEnabled || context.forumStore?.isModuleEnabled
  if (typeof checker === 'function') {
    return checker(moduleId)
  }
  return true
}

function matchesSurface(item, context = {}) {
  if (!Array.isArray(item?.surfaces) || item.surfaces.length === 0) {
    return true
  }
  const surface = normalizeKey(context.surface)
  return Boolean(surface && item.surfaces.includes(surface))
}

function upsertByKey(items, value) {
  const index = items.findIndex(item => item.key === value.key)
  if (index >= 0) {
    items.splice(index, 1, value)
    return value
  }
  items.push(value)
  return value
}

function clearRegistryCollections(registries, extensionId = '') {
  for (const registry of registries) {
    registry.clear(extensionId)
  }
}

function clearRegistryItems(targets, extensionId = '') {
  for (const items of targets) {
    clearItemsForExtension(items, extensionId)
  }
}

function clearItemsForExtension(items, extensionId = '') {
  const normalizedExtensionId = normalizeKey(extensionId)
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const itemExtensionId = normalizeKey(items[index]?.extensionId || items[index]?.extension_id)
    if (!itemExtensionId) {
      continue
    }
    if (!normalizedExtensionId || itemExtensionId === normalizedExtensionId) {
      items.splice(index, 1)
    }
  }
}

function withExtensionId(item, extensionId) {
  if (!extensionId || !item || typeof item !== 'object') {
    return item
  }
  return {
    ...item,
    extensionId: item.extensionId || item.extension_id || extensionId,
    extension_id: item.extension_id || item.extensionId || extensionId,
  }
}

function normalizeKey(value) {
  return String(value || '').trim()
}
