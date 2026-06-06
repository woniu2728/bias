import {
  createExtensionInitializers,
  createExtensionPatcher,
  runWithExtensionScope,
} from '../common/extensionRuntime.js'
import { createExtensionAppApi } from '../common/extensionAppApi.js'
import { createAdminRuntimeRegistry } from './runtimeRegistry.js'

const adminInitializers = createExtensionInitializers()
const adminPatcher = createExtensionPatcher()

export function createAdminExtensionApp({
  app: application,
  extension,
  loadedExtensionIds,
  registry = {},
  router,
} = {}) {
  const appApi = createExtensionAppApi({
    application,
    api: registry.adminApi,
    extension,
    store: application?.store || registry,
  })
  const initializers = application?.initializers || adminInitializers
  const scopedRegistry = appApi.items
  const registryApi = createAdminExtensionRegistryApi({
    registry,
    scopedRegistry,
    extensionId: extension?.id,
  })
  return Object.freeze({
    ...appApi,
    api: registry.adminApi,
    extension,
    initializers,
    extend: adminPatcher.extend,
    override: adminPatcher.override,
    resetPatches: adminPatcher.reset,
    loadedExtensionIds,
    router,
    registry: registryApi,
    items: scopedRegistry,
    runWithExtensionScope(callback) {
      return runWithExtensionScope(extension?.id, callback)
    },
  })
}

function createAdminExtensionRegistryApi({ registry = {}, scopedRegistry = null, extensionId = '' } = {}) {
  const base = registry && typeof registry.for === 'function'
    ? registry
    : createAdminRuntimeRegistry(registry || {})
  const baseFor = typeof base.for === 'function' ? base.for.bind(base) : null
  const normalizedExtensionId = String(extensionId || '').trim()
  const api = {
    ...(registry || {}),
    ...base,
    list: (...args) => scopedRegistry.list(...args),
    single: (...args) => scopedRegistry.single(...args),
    add: (...args) => scopedRegistry.add(...args),
    register: (...args) => scopedRegistry.register(...args),
    get: (...args) => scopedRegistry.get(...args),
    getByKey: (...args) => scopedRegistry.getByKey(...args),
    getOne: (...args) => scopedRegistry.getOne(...args),
    clear: (...args) => scopedRegistry.clear(...args),
  }
  api.for = (context = normalizedExtensionId) => {
    const normalizedContext = String(context || '').trim()
    baseFor?.(normalizedContext)
    return createScopedAdminRegistryContext(api, normalizedContext)
  }
  return api.for(normalizedExtensionId)
}

function createScopedAdminRegistryContext(registry, context = '') {
  const normalizedContext = String(context || '').trim()
  return new Proxy(registry, {
    get(target, property, receiver) {
      if (property === 'for') {
        return nextContext => createScopedAdminRegistryContext(target, nextContext || normalizedContext)
      }
      const value = Reflect.get(target, property, receiver)
      if (typeof value !== 'function') {
        return value
      }
      if (!String(property).startsWith('register')) {
        return value.bind(target)
      }
      return (definition, ...args) => value.call(target, withExtensionId(definition, normalizedContext), ...args)
    },
  })
}

function withExtensionId(value, extensionId) {
  if (!extensionId || !value || typeof value !== 'object') {
    return value
  }
  return {
    ...value,
    extensionId: value.extensionId || value.extension_id || extensionId,
    extension_id: value.extension_id || value.extensionId || extensionId,
  }
}

export function getAdminExtensionInitializers() {
  return adminInitializers
}

export function resetAdminExtensionAppRuntime(extensionId = '', { app } = {}) {
  if (app?.initializers && app.initializers !== adminInitializers) {
    app.initializers.clear(extensionId)
  }
  adminInitializers.clear(extensionId)
  adminPatcher.reset(extensionId)
  app?.application?.extensionRegistry?.clear?.(extensionId)
  app?.items?.clear?.()
}
