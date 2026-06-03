let currentExtensionId = ''
const patchRecords = []
const handledRuntimeErrors = new Set()
const runtimeErrors = []
const lazyModuleRegistry = new Map()
const lazyModuleListeners = new Map()

export function getCurrentExtensionId() {
  return currentExtensionId
}

export function runWithExtensionScope(extensionId, callback) {
  const previous = currentExtensionId
  currentExtensionId = String(extensionId || '').trim()
  try {
    return callback()
  } finally {
    currentExtensionId = previous
  }
}

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
    list() {
      return [...items].sort((left, right) => {
        const priority = (right.priority || 0) - (left.priority || 0)
        return priority || left.order - right.order
      })
    },
    async run(app, { onError } = {}) {
      const errors = []
      for (const initializer of this.list()) {
        try {
          await runWithExtensionScope(initializer.extensionId, () => initializer.callback(app))
        } catch (error) {
          errors.push({ extensionId: initializer.extensionId, error })
          if (typeof onError === 'function') {
            onError(error, initializer.extensionId)
          }
        }
      }
      return errors
    },
    async runWithAppResolver(resolveApp, { onError } = {}) {
      const errors = []
      for (const initializer of this.list()) {
        const app = typeof resolveApp === 'function' ? resolveApp(initializer.extensionId) : null
        try {
          await runWithExtensionScope(initializer.extensionId, () => initializer.callback(app))
        } catch (error) {
          errors.push({ extensionId: initializer.extensionId, error })
          if (typeof onError === 'function') {
            onError(error, initializer.extensionId)
          }
        }
      }
      return errors
    },
  })
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
    return onLazyModuleLoad(target, module => extendMethod(resolveLazyModuleTarget(module), methods, callback, { extensionId: normalizedExtensionId }))
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
    return onLazyModuleLoad(target, module => overrideMethod(resolveLazyModuleTarget(module), methods, callback, { extensionId: normalizedExtensionId }))
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
  for (let index = patchRecords.length - 1; index >= 0; index -= 1) {
    const record = patchRecords[index]
    if (normalizedExtensionId && record.extensionId !== normalizedExtensionId) {
      continue
    }
    record.target[record.method] = record.original
    patchRecords.splice(index, 1)
  }
}

export function registerLazyExtensionModule(key, module) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) {
    return false
  }
  lazyModuleRegistry.set(normalizedKey, module)
  const listeners = lazyModuleListeners.get(normalizedKey) || []
  lazyModuleListeners.delete(normalizedKey)
  for (const listener of listeners) {
    listener(module)
  }
  return true
}

export function onLazyModuleLoad(key, callback) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey || typeof callback !== 'function') {
    return false
  }
  if (lazyModuleRegistry.has(normalizedKey)) {
    callback(lazyModuleRegistry.get(normalizedKey))
    return true
  }
  const listeners = lazyModuleListeners.get(normalizedKey) || []
  listeners.push(callback)
  lazyModuleListeners.set(normalizedKey, listeners)
  return true
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
