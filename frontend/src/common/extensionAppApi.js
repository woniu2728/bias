import { getExtensionRuntimeErrors, handleExtensionRuntimeError } from './extensionRuntime.js'
import { ensureExportRegistry } from './exportRegistry.js'
import ItemList from './itemList.js'
import { createExtensionRegistry } from './listRegistry.js'

export function createExtensionAppApi({
  application = null,
  api,
  extension,
  store = null,
  session = null,
  alerts = null,
  translator = null,
} = {}) {
  const cache = Object.create(null)
  const extensionId = String(extension?.id || '').trim()
  const extensionRegistry = application?.extensionRegistry || createExtensionRegistry()
  const exportRegistry = application?.exportRegistry || ensureExportRegistry()
  const scopedRegistry = extensionRegistry.scoped(extensionId)

  return {
    application,
    api: api || application?.api,
    extension,
    cache: application?.cache || cache,
    store: store || application?.store,
    route: application?.route,
    routes: application?.routes,
    search: application?.search,
    ItemList,
    items: scopedRegistry,
    extensionRegistry: scopedRegistry,
    exportRegistry,
    notificationComponents: application?.notificationComponents,
    postComponents: application?.postComponents,
    session: session || application?.session || createSessionApi(),
    alerts: alerts || application?.alerts || createAlertsApi(),
    translator: translator || application?.translator || createTranslatorApi(),
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
