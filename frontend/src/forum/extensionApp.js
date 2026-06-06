import api from '../api/index.js'
import { createExtensionAppApi } from '../common/extensionAppApi.js'
import {
  registerExtensionDocumentContent,
  registerExtensionTitleDriver,
} from './documentRuntime.js'
import {
  createExtensionInitializers,
  createExtensionPatcher,
  runWithExtensionScope,
} from '../common/extensionRuntime.js'

const forumInitializers = createExtensionInitializers()
const forumPatcher = createExtensionPatcher()

export function createForumExtensionApp({
  app: application,
  extension,
  forumStore,
  loadedExtensionIds,
  registry = {},
  registeredRoutes = [],
  router,
} = {}) {
  const appApi = createExtensionAppApi({
    application,
    api,
    extension,
    store: application?.store || forumStore,
  })
  const initializers = application?.initializers || forumInitializers
  const scopedRegistry = appApi.items
  const registryApi = createForumExtensionRegistryApi({
    registry,
    scopedRegistry,
    extensionId: extension?.id,
  })
  return Object.freeze({
    ...appApi,
    api,
    extension,
    initializers,
    extend: forumPatcher.extend,
    override: forumPatcher.override,
    resetPatches: forumPatcher.reset,
    forumStore,
    loadedExtensionIds,
    registeredRoutes,
    router,
    registry: registryApi,
    items: scopedRegistry,
    documentRuntime: {
      registerTitleDriver: registerExtensionTitleDriver,
      registerContent: registerExtensionDocumentContent,
    },
    runWithExtensionScope(callback) {
      return runWithExtensionScope(extension?.id, callback)
    },
  })
}

function createForumExtensionRegistryApi({ registry = {}, scopedRegistry = null, extensionId = '' } = {}) {
  const normalizedExtensionId = String(extensionId || '').trim()
  const api = {
    ...(registry || {}),
    list: (...args) => scopedRegistry.list(...args),
    single: (...args) => scopedRegistry.single(...args),
    add: (...args) => scopedRegistry.add(...args),
    register: (...args) => scopedRegistry.register(...args),
    get: (...args) => scopedRegistry.get(...args),
    getByKey: (...args) => scopedRegistry.getByKey(...args),
    getOne: (...args) => scopedRegistry.getOne(...args),
    clear: (...args) => scopedRegistry.clear(...args),
  }
  api.for = (context = normalizedExtensionId) => createScopedForumRegistryContext(api, context)
  return api.for(normalizedExtensionId)
}

function createScopedForumRegistryContext(registry, context = '') {
  const normalizedContext = String(context || '').trim()
  return new Proxy(registry, {
    get(target, property, receiver) {
      if (property === 'for') {
        return nextContext => createScopedForumRegistryContext(target, nextContext || normalizedContext)
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

export function getForumExtensionInitializers() {
  return forumInitializers
}

export function resetForumExtensionAppRuntime(extensionId = '', { app } = {}) {
  if (app?.initializers && app.initializers !== forumInitializers) {
    app.initializers.clear(extensionId)
  }
  forumInitializers.clear(extensionId)
  forumPatcher.reset(extensionId)
  app?.application?.extensionRegistry?.clear?.(extensionId)
  app?.items?.clear?.()
}
