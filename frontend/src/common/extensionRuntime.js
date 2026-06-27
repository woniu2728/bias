import { ensureExportRegistry } from './exportRegistry.js'
import { getCurrentExtensionId, runWithExtensionScope } from './extensionScope.js'
import ItemList from './itemList.js'

const patchRecords = []
const lazyPatchRecords = []
const handledRuntimeErrors = new Set()
const runtimeErrors = []
const lazyModuleRegistry = new Map()

export { getCurrentExtensionId, runWithExtensionScope }

export function createExtensionInitializers() {
  const items = []

  return Object.freeze({
    add(extensionId, callback, priority = 0) {
      const normalizedExtensionId = String(extensionId || getCurrentExtensionId() || '').trim()
      if (!normalizedExtensionId || typeof callback !== 'function') {
        return false
      }
      items.push({
        extensionId: normalizedExtensionId,
        callback,
        priority: Number.parseInt(priority, 10) || 0,
        order: items.length,
      })
      return true
    },
    clear(extensionId = '') {
      const normalizedExtensionId = String(extensionId || '').trim()
      if (!normalizedExtensionId) {
        items.splice(0, items.length)
        return
      }
      removeMatching(items, item => item.extensionId === normalizedExtensionId)
    },
    remove(extensionId = '') {
      this.clear(extensionId)
      return this
    },
    has(extensionId = '') {
      const normalizedExtensionId = String(extensionId || '').trim()
      return items.some(item => item.extensionId === normalizedExtensionId)
    },
    get(extensionId = '') {
      const normalizedExtensionId = String(extensionId || '').trim()
      return items.find(item => item.extensionId === normalizedExtensionId)?.callback || null
    },
    list() {
      return [...items].sort((left, right) => {
        const priority = (right.priority || 0) - (left.priority || 0)
        return priority || left.order - right.order
      })
    },
    toItemList() {
      const list = new ItemList()
      for (const initializer of items) {
        list.add(
          initializerName(initializer),
          initializer.callback,
          initializer.priority
        )
      }
      return list
    },
    toArray(options = false) {
      return this.toItemList().toArray(options)
    },
    toObject() {
      return this.toItemList().toObject()
    },
    async run(app, { onError } = {}) {
      const errors = []
      for (const initializer of this.list()) {
        const contextApp = resolveInitializerContextApp(app)
        const previousInitializerExtension = contextApp?.currentInitializerExtension ?? null
        if (contextApp && 'currentInitializerExtension' in contextApp) {
          contextApp.currentInitializerExtension = initializer.extensionId
        }
        try {
          await runWithExtensionScope(initializer.extensionId, () => initializer.callback(app))
        } catch (error) {
          errors.push({ extensionId: initializer.extensionId, error })
          if (typeof onError === 'function') {
            onError(error, initializer.extensionId)
          }
        } finally {
          if (contextApp && 'currentInitializerExtension' in contextApp) {
            contextApp.currentInitializerExtension = previousInitializerExtension
          }
        }
      }
      return errors
    },
    async runWithAppResolver(resolveApp, { onError } = {}) {
      const errors = []
      for (const initializer of this.list()) {
        const app = typeof resolveApp === 'function' ? resolveApp(initializer.extensionId) : null
        const contextApp = resolveInitializerContextApp(app)
        const previousInitializerExtension = contextApp?.currentInitializerExtension ?? null
        if (contextApp && 'currentInitializerExtension' in contextApp) {
          contextApp.currentInitializerExtension = initializer.extensionId
        }
        try {
          await runWithExtensionScope(initializer.extensionId, () => initializer.callback(app))
        } catch (error) {
          errors.push({ extensionId: initializer.extensionId, error })
          if (typeof onError === 'function') {
            onError(error, initializer.extensionId)
          }
        } finally {
          if (contextApp && 'currentInitializerExtension' in contextApp) {
            contextApp.currentInitializerExtension = previousInitializerExtension
          }
        }
      }
      return errors
    },
  })
}

function initializerName(initializer) {
  const suffix = Number.isFinite(initializer.order) ? initializer.order : 0
  return `${initializer.extensionId}/${suffix}`
}

function resolveInitializerContextApp(app) {
  return app?.application || app || null
}

export function createExtensionPatcher() {
  return Object.freeze({
    extend: extendMethod,
    override: overrideMethod,
    reset(extensionId = '') {
      resetExtensionPatches(extensionId)
    },
  })
}

export function extendMethod(target, methods, callback, { extensionId = getCurrentExtensionId() } = {}) {
  const normalizedExtensionId = String(extensionId || '').trim()
  if (typeof target === 'string') {
    return registerLazyMethodPatch('extend', target, methods, callback, { extensionId: normalizedExtensionId })
  }
  if (!target || typeof callback !== 'function') {
    return false
  }
  for (const method of normalizeMethods(methods)) {
    const original = target[method]
    target[method] = function extensionRuntimeExtendedMethod(...args) {
      const value = typeof original === 'function' ? original.apply(this, args) : undefined
      try {
        callback.apply(this, [value, ...args])
      } catch (error) {
        handleExtensionRuntimeError(error, normalizedExtensionId, `extend:${String(method)}`)
      }
      return value
    }
    copyFunctionMetadata(target[method], original)
    patchRecords.push({ extensionId: normalizedExtensionId, target, method, original })
  }
  return true
}

export function overrideMethod(target, methods, callback, { extensionId = getCurrentExtensionId() } = {}) {
  const normalizedExtensionId = String(extensionId || '').trim()
  if (typeof target === 'string') {
    return registerLazyMethodPatch('override', target, methods, callback, { extensionId: normalizedExtensionId })
  }
  if (!target || typeof callback !== 'function') {
    return false
  }
  for (const method of normalizeMethods(methods)) {
    const original = target[method]
    target[method] = function extensionRuntimeOverriddenMethod(...args) {
      try {
        return callback.apply(this, [
          typeof original === 'function' ? original.bind(this) : () => undefined,
          ...args,
        ])
      } catch (error) {
        handleExtensionRuntimeError(error, normalizedExtensionId, `override:${String(method)}`)
        return undefined
      }
    }
    copyFunctionMetadata(target[method], original)
    patchRecords.push({ extensionId: normalizedExtensionId, target, method, original })
  }
  return true
}

export function resetExtensionPatches(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (let index = lazyPatchRecords.length - 1; index >= 0; index -= 1) {
    const record = lazyPatchRecords[index]
    if (normalizedExtensionId && record.extensionId !== normalizedExtensionId) {
      continue
    }
    record.active = false
    lazyPatchRecords.splice(index, 1)
  }
  for (let index = patchRecords.length - 1; index >= 0; index -= 1) {
    const record = patchRecords[index]
    if (normalizedExtensionId && record.extensionId !== normalizedExtensionId) {
      continue
    }
    record.target[record.method] = record.original
    patchRecords.splice(index, 1)
  }
}

function registerLazyMethodPatch(kind, key, methods, callback, { extensionId = '' } = {}) {
  const normalizedKey = String(key || '').trim()
  const normalizedExtensionId = String(extensionId || '').trim()
  if (!normalizedKey || typeof callback !== 'function') {
    return false
  }

  const record = {
    active: true,
    extensionId: normalizedExtensionId,
    key: normalizedKey,
    kind,
    methods,
    callback,
  }
  lazyPatchRecords.push(record)

  const registered = onLazyModuleLoad(normalizedKey, module => {
    if (!record.active) {
      return
    }
    record.active = false
    removeMatching(lazyPatchRecords, item => item === record)
    const resolvedTarget = resolveLazyModuleTarget(module)
    if (kind === 'override') {
      overrideMethod(resolvedTarget, methods, callback, { extensionId: normalizedExtensionId })
      return
    }
    extendMethod(resolvedTarget, methods, callback, { extensionId: normalizedExtensionId })
  })

  if (!registered) {
    record.active = false
    removeMatching(lazyPatchRecords, item => item === record)
  }
  return registered
}

export function registerLazyExtensionModule(key, module, { extensionId = getCurrentExtensionId() } = {}) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) {
    return false
  }
  const normalizedExtensionId = String(extensionId || extensionIdFromRuntimeKey(normalizedKey) || '').trim()
  ensureBiasNamespace().reg.registerModule(normalizedKey, module)
  lazyModuleRegistry.set(normalizedKey, {
    extensionId: normalizedExtensionId,
    module,
  })
  return true
}

export function registerLoadedExtensionModule(extensionId, module, {
  app = null,
  extension = null,
  frontend = '',
  entryPath = '',
} = {}) {
  const normalizedExtensionId = String(extensionId || extension?.id || '').trim()
  if (!normalizedExtensionId || !module) {
    return null
  }

  const namespace = ensureBiasNamespace()
  const normalizedFrontend = String(frontend || 'default').trim() || 'default'
  const globalRecord = namespace.extensions[normalizedExtensionId] || createLoadedExtensionRecord(normalizedExtensionId)
  const targetRecord = app?.extensions
    ? (app.extensions[normalizedExtensionId] || globalRecord)
    : globalRecord
  const record = mergeLoadedExtensionRecord(targetRecord, {
    extensionId: normalizedExtensionId,
    module,
    extension,
    frontend,
    entryPath,
  })

  namespace.extensions[normalizedExtensionId] = record
  namespace.reg.register(normalizedExtensionId, normalizedFrontend, module)
  if (entryPath) {
    namespace.reg.registerModule(entryPath, module)
  }
  if (app?.extensions) {
    app.extensions[normalizedExtensionId] = record
  }
  if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
    globalThis.dispatchEvent(new CustomEvent('bias:extension-module-registered', { detail: record }))
  }
  return record
}

export function unregisterLoadedExtensionModule(extensionId = '', { app = null } = {}) {
  const normalizedExtensionId = String(extensionId || '').trim()
  const namespace = ensureBiasNamespace()
  if (!normalizedExtensionId) {
    for (const key of Object.keys(namespace.extensions)) {
      delete namespace.extensions[key]
    }
    if (app?.extensions) {
      for (const key of Object.keys(app.extensions)) {
        delete app.extensions[key]
      }
    }
    namespace.reg.clear()
    unregisterLazyExtensionModules()
    return
  }
  delete namespace.extensions[normalizedExtensionId]
  if (app?.extensions) {
    delete app.extensions[normalizedExtensionId]
  }
  namespace.reg.clearNamespace?.(normalizedExtensionId)
  app?.exportRegistry?.clearNamespace?.(normalizedExtensionId)
  unregisterLazyExtensionModules(normalizedExtensionId)
}

export function onLazyModuleLoad(key, callback) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey || typeof callback !== 'function') {
    return false
  }
  const registry = ensureBiasNamespace().reg
  const registeredModule = registry.getModule(normalizedKey)
  if (registeredModule) {
    callback(registeredModule)
    return true
  }
  if (lazyModuleRegistry.has(normalizedKey)) {
    callback(lazyModuleRegistry.get(normalizedKey).module)
    return true
  }
  return registry.onLoadPath(normalizedKey, callback)
}

export function unregisterLazyExtensionModules(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  const registry = ensureBiasNamespace().reg
  if (!normalizedExtensionId) {
    for (const key of lazyModuleRegistry.keys()) {
      registry.unregisterModule?.(key)
    }
    lazyModuleRegistry.clear()
    return
  }
  for (const [key, record] of [...lazyModuleRegistry.entries()]) {
    if (record.extensionId === normalizedExtensionId || extensionIdFromRuntimeKey(key) === normalizedExtensionId) {
      registry.unregisterModule?.(key)
      lazyModuleRegistry.delete(key)
    }
  }
}

export function getExtensionRuntimeErrors() {
  return [...runtimeErrors]
}

export function clearExtensionRuntimeErrors(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (let index = runtimeErrors.length - 1; index >= 0; index -= 1) {
    if (!normalizedExtensionId || runtimeErrors[index].extensionId === normalizedExtensionId) {
      runtimeErrors.splice(index, 1)
    }
  }
  if (!normalizedExtensionId) {
    handledRuntimeErrors.clear()
    return
  }
  for (const key of [...handledRuntimeErrors]) {
    if (key.startsWith(`${normalizedExtensionId}:`)) {
      handledRuntimeErrors.delete(key)
    }
  }
}

export function handleExtensionRuntimeError(error, extensionId = '', operation = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  const normalizedOperation = String(operation || '').trim()
  const errorKey = `${normalizedExtensionId}:${normalizedOperation}:${String(error?.message || error || '')}`
  if (handledRuntimeErrors.has(errorKey)) {
    return
  }
  handledRuntimeErrors.add(errorKey)
  const details = {
    extensionId: normalizedExtensionId,
    operation: normalizedOperation,
    error,
    message: String(error?.message || error || ''),
    occurredAt: new Date().toISOString(),
  }
  runtimeErrors.push(details)
  if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
    globalThis.dispatchEvent(new CustomEvent('bias:extension-runtime-error', { detail: details }))
    return
  }
  if (globalThis.console && typeof globalThis.console.error === 'function') {
    globalThis.console.error('Extension runtime error', details)
  }
}

function resolveLazyModuleTarget(module) {
  return module?.default?.prototype || module?.prototype || module?.default || module
}

function extensionIdFromRuntimeKey(key) {
  const parts = String(key || '').trim().replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[0] === 'extensions' && parts[1] ? parts[1] : ''
}

function ensureBiasNamespace() {
  if (!globalThis.bias || typeof globalThis.bias !== 'object') {
    globalThis.bias = {}
  }
  ensureExportRegistry(globalThis)
  if (!globalThis.bias.extensions || typeof globalThis.bias.extensions !== 'object') {
    globalThis.bias.extensions = Object.create(null)
  }
  return globalThis.bias
}

function createLoadedExtensionRecord(extensionId) {
  return {
    id: extensionId,
    extension: null,
    module: null,
    exports: null,
    modules: Object.create(null),
    entryPaths: Object.create(null),
    registeredAt: '',
  }
}

function mergeLoadedExtensionRecord(record, {
  extensionId,
  module,
  extension,
  frontend,
  entryPath,
}) {
  const normalizedFrontend = String(frontend || 'default').trim() || 'default'
  record.id = extensionId
  record.extension = extension || record.extension || null
  record.module = module
  record.exports = module
  record.modules[normalizedFrontend] = module
  if (entryPath) {
    record.entryPaths[normalizedFrontend] = String(entryPath)
  }
  record.registeredAt = new Date().toISOString()
  return record
}

function normalizeMethods(methods) {
  return (Array.isArray(methods) ? methods : [methods])
    .map(method => String(method || '').trim())
    .filter(Boolean)
}

function copyFunctionMetadata(target, original) {
  if (!target || !original || typeof original !== 'function') {
    return
  }
  Object.assign(target, original)
}

function removeMatching(items, predicate) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) {
      items.splice(index, 1)
    }
  }
}
