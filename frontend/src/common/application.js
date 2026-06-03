export function createRuntimeApplication({
  kind,
  vueApp,
  router,
  pinia,
  api,
  store = null,
  session = null,
  alerts = null,
  translator = null,
} = {}) {
  const cache = Object.create(null)
  const bootingCallbacks = []
  const bootedCallbacks = []
  const errors = []
  let booted = false

  const app = {
    kind: String(kind || 'app'),
    vueApp,
    router,
    pinia,
    api,
    store,
    session: session || createSessionApi(),
    alerts: alerts || createAlertApi(),
    translator: translator || createTranslatorApi(),
    cache,
    errors,
    get booted() {
      return booted
    },
    booting(callback) {
      if (typeof callback === 'function') bootingCallbacks.push(callback)
    },
    booted(callback) {
      if (typeof callback === 'function') bootedCallbacks.push(callback)
    },
    async boot(callback) {
      for (const item of bootingCallbacks.splice(0)) {
        await item(app)
      }
      if (typeof callback === 'function') {
        await callback(app)
      }
      booted = true
      for (const item of bootedCallbacks.splice(0)) {
        await item(app)
      }
      return app
    },
    handleError(error, operation = 'application') {
      const details = {
        operation,
        error,
        message: String(error?.message || error || ''),
        occurredAt: new Date().toISOString(),
      }
      errors.push(details)
      if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
        globalThis.dispatchEvent(new CustomEvent('bias:application-error', { detail: details }))
      }
      return details
    },
  }

  return app
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

function createAlertApi() {
  return {
    show(message, options = {}) {
      const detail = {
        message: String(message || ''),
        tone: options.tone || 'info',
        title: options.title || '',
      }
      if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
        globalThis.dispatchEvent(new CustomEvent('bias:application-alert', { detail }))
      }
      return detail
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
