import { createExtensionInitializers, runWithExtensionScope } from './extensionRuntime.js'
import { registerDefaultResourceModels } from './resourceModels.js'
import { createResourceStoreAdapter } from './resourceStoreAdapter.js'
import { createExtensionRegistry } from './listRegistry.js'
import { ensureExportRegistry } from './exportRegistry.js'

export function createRuntimeApplication({
  kind,
  vueApp,
  router,
  pinia,
  api,
  store = null,
  resourceStore = null,
  forumStore = null,
  registry = null,
  session = null,
  alerts = null,
  translator = null,
} = {}) {
  const cache = Object.create(null)
  const bootingCallbacks = []
  const bootedCallbacks = []
  const beforeMountCallbacks = []
  const initializers = createExtensionInitializers()
  const extensions = Object.create(null)
  const extensionRegistry = createExtensionRegistry()
  const exportRegistry = ensureExportRegistry()
  const errors = []
  const data = {
    apiDocument: null,
    resources: [],
    session: {},
  }
  let booted = false
  let initialRoute = ''
  let title = ''
  let titleCount = 0
  let currentInitializerExtension = null

  const app = {
    kind: String(kind || 'app'),
    vueApp,
    router,
    pinia,
    api,
    registry,
    store,
    resourceStore,
    forumStore: forumStore || null,
    notificationComponents: Object.create(null),
    postComponents: Object.create(null),
    routeHelpers: Object.create(null),
    routes: {
      definitions: Object.create(null),
      helpers: Object.create(null),
    },
    search: {
      gambits: {
        gambits: Object.create(null),
        apply(modelType, filter = {}) {
          return applySearchGambits(app, modelType, filter)
        },
      },
    },
    session: session || createSessionApi(),
    alerts: alerts || createAlertApi(),
    translator: translator || createTranslatorApi(),
    initializers,
    extensions,
    extensionRegistry,
    exportRegistry,
    items: extensionRegistry,
    cache,
    data,
    errors,
    get initialRoute() {
      return initialRoute
    },
    get title() {
      return title
    },
    get titleCount() {
      return titleCount
    },
    get booted() {
      return booted
    },
    get currentInitializerExtension() {
      return currentInitializerExtension
    },
    set currentInitializerExtension(value) {
      currentInitializerExtension = value == null ? null : String(value || '').trim()
    },
    extension(extensionId) {
      return extensions[String(extensionId || '').trim()] || null
    },
    load(payload = {}) {
      Object.assign(data, normalizeApplicationPayload(payload))
      if (app.session && typeof app.session.load === 'function') {
        app.session.load(data.session)
      }
      return app
    },
    booting(callback) {
      if (typeof callback === 'function') bootingCallbacks.push(callback)
    },
    booted(callback) {
      if (typeof callback === 'function') bootedCallbacks.push(callback)
    },
    beforeMount(callback) {
      if (typeof callback === 'function') beforeMountCallbacks.push(callback)
    },
    async runBeforeMount() {
      for (const item of beforeMountCallbacks.splice(0)) {
        await item(app)
      }
      return app
    },
    async bootExtensions(extensions = {}, { createExtensionApp, onError } = {}) {
      for (const [extensionId, extension] of normalizeExtensionEntries(extensions)) {
        const extenders = normalizeExtensionExtenders(extension)
        const extensionApp = typeof createExtensionApp === 'function'
          ? createExtensionApp(extensionId, extension, app)
          : app
        for (const extender of extenders) {
          const previousInitializerExtension = app.currentInitializerExtension
          app.currentInitializerExtension = extensionId
          try {
            await runWithExtensionScope(extensionId, () => extender.extend(extensionApp, {
              name: extensionId,
              exports: extension,
            }))
          } catch (error) {
            app.handleError(error, `extension:${extensionId}:extender`)
            if (typeof onError === 'function') onError(error, extensionId)
          } finally {
            app.currentInitializerExtension = previousInitializerExtension
          }
        }
      }
      return app
    },
    async boot(callback) {
      for (const item of bootingCallbacks.splice(0)) {
        await item(app)
      }
      if (typeof callback === 'function') {
        await callback(app)
      }
      await app.runBeforeMount()
      initialRoute = getCurrentLocation()
      booted = true
      for (const item of bootedCallbacks.splice(0)) {
        await item(app)
      }
      return app
    },
    preloadedApiDocument() {
      if (!data.apiDocument || (initialRoute && getCurrentLocation() !== initialRoute)) {
        return null
      }
      const document = data.apiDocument
      data.apiDocument = null
      if (app.store && typeof app.store.mergePayload === 'function') {
        app.store.mergePayload(document)
      }
      return document
    },
    route(name, params = {}) {
      if (typeof name === 'string') {
        const helper = app.routes?.helpers?.[name] || app.routeHelpers?.[name]
        if (typeof helper === 'function') {
          return helper(params)
        }
      }
      if (!router || typeof router.resolve !== 'function') {
        return resolveRegisteredRoute(app, name, params)
      }
      const location = typeof name === 'object'
        ? name
        : normalizeRouteLocation(name, params)
      try {
        return router.resolve(location).href
      } catch (error) {
        if (typeof name === 'object') {
          throw error
        }
        return resolveRegisteredRoute(app, name, params, error)
      }
    },
    async request(options = {}) {
      if (!api) {
        throw new Error('Application API service is not configured')
      }
      const normalized = app.transformRequestOptions(options)
      try {
        let result
        if (typeof api.request === 'function') {
          result = await api.request(normalized)
        } else {
          const method = String(normalized.method || 'get').toLowerCase()
          if (typeof api[method] !== 'function') {
            throw new Error(`Unsupported request method: ${method}`)
          }
          if (['get', 'delete', 'head', 'options'].includes(method)) {
            result = await api[method](normalized.url, normalized)
          } else {
            result = await api[method](normalized.url, normalized.data, normalized)
          }
        }
        return app.deserializeRequestResponse(result, normalized)
      } catch (error) {
        const requestError = app.normalizeRequestError(error, normalized)
        const useDefaultHandler = typeof normalized.errorHandler !== 'function'
          || await normalized.errorHandler(requestError) === false
        app.handleError(requestError, `request:${normalized.method}:${normalized.url}`)
        if (useDefaultHandler) {
          app.requestErrorDefaultHandler(requestError)
        }
        throw requestError
      }
    },
    transformRequestOptions(options = {}) {
      const normalized = normalizeRequestOptions(options)
      normalized.headers = {
        ...(normalized.headers || {}),
      }
      if (!isSafeMethod(normalized.method)) {
        const csrfToken = app.session?.csrfToken
        if (csrfToken && !hasHeader(normalized.headers, 'X-CSRFToken') && !hasHeader(normalized.headers, 'X-CSRF-Token')) {
          normalized.headers['X-CSRFToken'] = csrfToken
        }
      }
      return normalized
    },
    deserializeRequestResponse(result, options = {}) {
      const envelope = normalizeResponseEnvelope(result)
      updateSessionCsrfToken(app.session, envelope.headers)
      let payload = envelope.data
      if (typeof options.modifyText === 'function' && typeof payload === 'string') {
        payload = options.modifyText(payload)
      }
      if (typeof options.extract === 'function') {
        payload = options.extract(envelope)
      }
      if (options.deserialize === false) {
        return payload
      }
      if (typeof options.deserialize === 'function') {
        return options.deserialize(payload)
      }
      return deserializeResponsePayload(payload)
    },
    normalizeRequestError(error, options = {}) {
      if (error instanceof ApplicationRequestError) {
        updateSessionCsrfToken(app.session, error.headers)
        return error
      }
      const response = error?.response || null
      const headers = normalizeHeaders(response?.headers || error?.headers || {})
      updateSessionCsrfToken(app.session, headers)
      const status = Number(response?.status || error?.status || 0)
      const data = response?.data ?? error?.data ?? null
      return new ApplicationRequestError({
        message: resolveRequestErrorMessage(error, data, status),
        status,
        response: data,
        headers,
        options,
        raw: error,
      })
    },
    requestErrorDefaultHandler(error) {
      const message = resolveDefaultRequestErrorMessage(error)
      error.alert = {
        type: 'error',
        content: message,
        status: error.status,
      }
      if (app.alerts && typeof app.alerts.error === 'function') {
        app.alerts.error(message, { title: resolveDefaultRequestErrorTitle(error) })
      } else if (app.alerts && typeof app.alerts.show === 'function') {
        app.alerts.show(message, { tone: 'danger', title: resolveDefaultRequestErrorTitle(error) })
      }
      if (typeof console !== 'undefined' && typeof console.error === 'function') {
        console.error(error)
      }
    },
    setTitle(value) {
      title = String(value || '')
      app.updateTitle()
    },
    setTitleCount(value) {
      titleCount = Number.parseInt(value, 10) || 0
      app.updateTitle()
    },
    updateTitle() {
      const parts = []
      if (titleCount) parts.push(`(${titleCount})`)
      if (title) parts.push(title)
      const text = parts.join(' ')
      if (text && globalThis.document) {
        globalThis.document.title = text
      }
      return text
    },
    setColorScheme(scheme) {
      const normalized = String(scheme || '').trim()
      if (normalized && globalThis.document?.documentElement?.setAttribute) {
        globalThis.document.documentElement.setAttribute('data-theme', normalized)
      }
      return normalized
    },
    setColoredHeader(value) {
      if (globalThis.document?.documentElement?.setAttribute) {
        globalThis.document.documentElement.setAttribute('data-colored-header', value ? 'true' : 'false')
      }
      return Boolean(value)
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

  if (!app.store && resourceStore) {
    app.store = createResourceStoreAdapter({
      resourceStore,
      request: options => app.request(options),
      search: app.search,
    })
  }
  if (app.store && !app.store.search) {
    app.store.search = app.search
  }
  if (app.store) {
    registerDefaultResourceModels(app.store)
  }

  return app
}

function normalizeApplicationPayload(payload) {
  const value = payload && typeof payload === 'object' ? payload : {}
  return {
    ...value,
    apiDocument: value.apiDocument || value.api_document || null,
    resources: Array.isArray(value.resources) ? value.resources : [],
    session: value.session && typeof value.session === 'object' ? value.session : {},
  }
}

function getCurrentLocation() {
  return String(globalThis.location?.href || globalThis.document?.location?.href || '')
}

function normalizeExtensionEntries(extensions) {
  if (extensions instanceof Map) return [...extensions.entries()]
  if (Array.isArray(extensions)) {
    return extensions
      .map(extension => [String(extension?.id || extension?.name || '').trim(), extension])
      .filter(([id]) => id)
  }
  if (extensions && typeof extensions === 'object') return Object.entries(extensions)
  return []
}

export function normalizeExtensionExtenders(module) {
  return normalizeExtenders(resolveExtensionExtenderSource(module))
}

export function hasExtensionExtenders(module) {
  return normalizeExtensionExtenders(module).length > 0
}

function resolveExtensionExtenderSource(module) {
  if (!module) return null
  if (Object.prototype.hasOwnProperty.call(Object(module), 'extend')) {
    return module.extend
  }
  const defaultExport = module.default
  if (defaultExport && typeof defaultExport === 'object' && Object.prototype.hasOwnProperty.call(defaultExport, 'extend')) {
    return defaultExport.extend
  }
  return defaultExport
}

function normalizeExtenders(value) {
  if (!value) return []
  return [value]
    .flat(Infinity)
    .map(item => {
      if (!item) return null
      if (typeof item.extend === 'function') return item
      if (typeof item === 'function') {
        return {
          extend: item,
        }
      }
      return null
    })
    .filter(Boolean)
}

function normalizeRequestOptions(options) {
  if (typeof options === 'string') {
    return { method: 'get', url: options }
  }
  const value = options && typeof options === 'object' ? options : {}
  return {
    ...value,
    method: String(value.method || 'get').toLowerCase(),
    url: String(value.url || ''),
  }
}

function normalizeRouteLocation(name, params = {}) {
  const value = params && typeof params === 'object' ? { ...params } : {}
  const query = value.query && typeof value.query === 'object' ? value.query : {}
  const hash = value.hash ? String(value.hash) : ''
  delete value.query
  delete value.hash
  return {
    name,
    params: value,
    query,
    hash,
  }
}

function resolveRegisteredRoute(app, name, params = {}, fallbackError = null) {
  if (typeof name === 'object') {
    if (fallbackError) throw fallbackError
    throw new Error('Application router is not configured')
  }
  const route = app?.routes?.definitions?.[name]
  if (!route?.path) {
    if (fallbackError) throw fallbackError
    throw new Error(`Route '${name}' does not exist`)
  }
  const values = params && typeof params === 'object' ? { ...params } : {}
  const query = values.query && typeof values.query === 'object' ? values.query : {}
  const hash = values.hash ? String(values.hash) : ''
  delete values.query
  delete values.hash
  const consumed = new Set()
  const path = String(route.path || '').replace(/:([^/]+)/g, (match, key) => {
    consumed.add(key)
    const value = values[key]
    return encodeURIComponent(value == null ? '' : String(value))
  })
  const extraQuery = {}
  for (const [key, value] of Object.entries(values)) {
    if (!consumed.has(key) && value) {
      extraQuery[key] = value
    }
  }
  const queryString = new URLSearchParams({ ...extraQuery, ...query }).toString()
  return path + (queryString ? `?${queryString}` : '') + hash
}

function normalizeResponseEnvelope(result) {
  if (isResponseEnvelope(result)) {
    return {
      data: 'data' in result ? result.data : result,
      headers: normalizeHeaders(result.headers || {}),
      status: Number(result.status || 0),
      raw: result,
    }
  }
  return {
    data: result,
    headers: {},
    status: 0,
    raw: result,
  }
}

function isResponseEnvelope(value) {
  if (!value || typeof value !== 'object') return false
  return 'headers' in value || 'status' in value || 'config' in value || 'request' in value
}

function deserializeResponsePayload(payload) {
  if (typeof payload !== 'string') {
    return payload
  }
  const text = payload.trim()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return payload
  }
}

function normalizeHeaders(headers = {}) {
  if (!headers || typeof headers !== 'object') {
    return {}
  }
  if (typeof headers.entries === 'function') {
    return Object.fromEntries([...headers.entries()].map(([key, value]) => [String(key).toLowerCase(), value]))
  }
  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [String(key).toLowerCase(), value])
  )
}

function updateSessionCsrfToken(session, headers = {}) {
  if (!session) return
  const normalized = normalizeHeaders(headers)
  const csrfToken = normalized['x-csrftoken'] || normalized['x-csrf-token']
  if (csrfToken) {
    session.csrfToken = String(csrfToken)
  }
}

function isSafeMethod(method = 'get') {
  return ['get', 'head', 'options', 'trace'].includes(String(method || 'get').toLowerCase())
}

function hasHeader(headers = {}, name = '') {
  const target = String(name || '').toLowerCase()
  return Object.keys(headers || {}).some(key => String(key).toLowerCase() === target)
}

function resolveRequestErrorMessage(error, data, status) {
  if (error?.message) return String(error.message)
  const detail = Array.isArray(data?.errors) ? data.errors[0]?.detail : ''
  if (detail) return String(detail)
  if (data?.error) return String(data.error)
  return status ? `Request failed with status ${status}` : 'Request failed'
}

function resolveDefaultRequestErrorTitle(error) {
  if (error.status === 401 || error.status === 403) return '权限不足'
  if (error.status === 404 || error.status === 410) return '资源不存在'
  if (error.status === 429) return '请求过于频繁'
  return '请求失败'
}

function resolveDefaultRequestErrorMessage(error) {
  const errors = Array.isArray(error.response?.errors) ? error.response.errors : []
  const detail = errors.map(item => item?.detail).filter(Boolean).join('\n')
  if (detail) return detail
  if (error.response?.error) return String(error.response.error)
  if (error.status === 401 || error.status === 403) return '你没有权限执行该操作。'
  if (error.status === 404 || error.status === 410) return '请求的资源不存在。'
  if (error.status === 413) return '请求内容过大。'
  if (error.status === 429) return '请求过于频繁，请稍后再试。'
  return error.message || '请求失败，请稍后再试。'
}

export class ApplicationRequestError extends Error {
  constructor({ message, status = 0, response = null, headers = {}, options = {}, raw = null } = {}) {
    super(String(message || 'Request failed'))
    this.name = 'ApplicationRequestError'
    this.status = Number(status || 0)
    this.response = response
    this.headers = normalizeHeaders(headers)
    this.options = options
    this.raw = raw
    this.alert = null
  }
}

function createSessionApi(initial = {}) {
  let state = normalizeSessionState(initial)
  return {
    load(payload = {}) {
      state = normalizeSessionState(payload)
      return state
    },
    get user() {
      return state.user || null
    },
    get authenticated() {
      return Boolean(state.user || state.userId || state.user_id)
    },
    get csrfToken() {
      return state.csrfToken || state.csrf_token || ''
    },
    set csrfToken(value) {
      state.csrfToken = String(value || '')
    },
  }
}

function normalizeSessionState(payload) {
  return payload && typeof payload === 'object' ? { ...payload } : {}
}

function createAlertApi() {
  const dispatch = (tone, message, options = {}) => {
    const detail = {
      message: String(message || ''),
      tone,
      title: options.title || '',
      timeout: options.timeout,
    }
    if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
      globalThis.dispatchEvent(new CustomEvent('bias:application-alert', { detail }))
    }
    return detail
  }

  return {
    show(message, options = {}) {
      return dispatch(options.tone || 'info', message, options)
    },
    info(message, options = {}) {
      return dispatch('info', message, options)
    },
    success(message, options = {}) {
      return dispatch('success', message, options)
    },
    warning(message, options = {}) {
      return dispatch('warning', message, options)
    },
    error(message, options = {}) {
      return dispatch('danger', message, options)
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

function applySearchGambits(app, modelType, filter = {}) {
  const normalizedType = normalizeSearchTarget(modelType)
  const items = [
    ...(app.search?.gambits?.gambits?.all || []),
    ...(app.search?.gambits?.gambits?.[normalizedType] || []),
  ]
  if (!items.length) {
    return filter
  }

  let output = { ...(filter || {}) }
  for (const gambit of items) {
    const result = runSearchGambit(gambit, output.q || '', output, {
      app,
      modelType: normalizedType,
    })
    if (typeof result === 'string') {
      output = { ...output, q: result }
    } else if (result && typeof result === 'object') {
      output = { ...output, ...result }
    }
  }
  return output
}

function runSearchGambit(gambit, query, filter, context) {
  if (!gambit) return null
  if (typeof gambit === 'function') {
    const instance = createGambitInstance(gambit)
    if (instance && typeof instance.apply === 'function') {
      return instance.apply(query, filter, context)
    }
    return gambit(query, filter, context)
  }
  if (typeof gambit.apply === 'function') {
    return gambit.apply(query, filter, context)
  }
  if (typeof gambit.transform === 'function') {
    return gambit.transform(query, filter, context)
  }
  return null
}

function createGambitInstance(Gambit) {
  try {
    if (Gambit.prototype && typeof Gambit.prototype.apply === 'function') {
      return new Gambit()
    }
  } catch {
    return null
  }
  return null
}

function normalizeSearchTarget(target = '') {
  const normalized = String(target || '').trim().toLowerCase()
  if (['discussion', 'discussions'].includes(normalized)) return 'discussions'
  if (['post', 'posts'].includes(normalized)) return 'posts'
  if (['user', 'users'].includes(normalized)) return 'users'
  return normalized || 'all'
}
