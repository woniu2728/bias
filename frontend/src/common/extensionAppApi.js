import { getExtensionRuntimeErrors, handleExtensionRuntimeError } from './extensionRuntime.js'

export function createExtensionAppApi({
  api,
  extension,
  store = null,
  session = null,
  alerts = null,
  translator = null,
} = {}) {
  const cache = Object.create(null)
  const extensionId = String(extension?.id || '').trim()

  return {
    api,
    extension,
    cache,
    store,
    session: session || createSessionApi(),
    alerts: alerts || createAlertsApi(),
    translator: translator || createTranslatorApi(),
    errors: {
      list() {
        return getExtensionRuntimeErrors().filter(error => !extensionId || error.extensionId === extensionId)
      },
      report(error, operation = 'extension-app') {
        return handleExtensionRuntimeError(error, extensionId, operation)
      },
    },
  }
}

function createSessionApi() {
  return {
    get user() {
      return null
    },
    get authenticated() {
      return false
    },
  }
}

function createAlertsApi() {
  return {
    info(message, options = {}) {
      return dispatchAlert('info', message, options)
    },
    success(message, options = {}) {
      return dispatchAlert('success', message, options)
    },
    warning(message, options = {}) {
      return dispatchAlert('warning', message, options)
    },
    error(message, options = {}) {
      return dispatchAlert('danger', message, options)
    },
  }
}

function createTranslatorApi() {
  return {
    trans(key, parameters = {}) {
      return Object.entries(parameters || {}).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        String(key || '')
      )
    },
  }
}

function dispatchAlert(tone, message, options = {}) {
  const detail = {
    tone,
    message: String(message || ''),
    title: options.title || '',
    timeout: options.timeout,
  }
  if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
    globalThis.dispatchEvent(new CustomEvent('bias:extension-alert', { detail }))
  }
  return detail
}
