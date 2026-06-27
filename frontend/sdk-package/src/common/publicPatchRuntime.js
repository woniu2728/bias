import { getCurrentExtensionId } from './extensionScope.js'

const patchRecords = []

export function extendMethod(target, methods, callback, { extensionId = getCurrentExtensionId() } = {}) {
  const normalizedExtensionId = String(extensionId || '').trim()
  if (!target || typeof target === 'string' || typeof callback !== 'function') {
    return false
  }
  for (const method of normalizeMethods(methods)) {
    const original = target[method]
    target[method] = function extensionRuntimeExtendedMethod(...args) {
      const value = typeof original === 'function' ? original.apply(this, args) : undefined
      try {
        callback.apply(this, [value, ...args])
      } catch (error) {
        handlePatchError(error, normalizedExtensionId, `extend:${String(method)}`)
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
  if (!target || typeof target === 'string' || typeof callback !== 'function') {
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
        handlePatchError(error, normalizedExtensionId, `override:${String(method)}`)
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

function handlePatchError(error, extensionId = '', operation = '') {
  const details = {
    extensionId,
    operation,
    error,
    message: String(error?.message || error || ''),
    occurredAt: new Date().toISOString(),
  }
  if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
    globalThis.dispatchEvent(new CustomEvent('bias:extension-runtime-error', { detail: details }))
    return
  }
  if (globalThis.console && typeof globalThis.console.error === 'function') {
    globalThis.console.error('Extension runtime error', details)
  }
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
