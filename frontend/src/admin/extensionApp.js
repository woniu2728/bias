import {
  createExtensionInitializers,
  createExtensionPatcher,
  runWithExtensionScope,
} from '../common/extensionRuntime.js'
import { createExtensionAppApi } from '../common/extensionAppApi.js'

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
    registry,
    runWithExtensionScope(callback) {
      return runWithExtensionScope(extension?.id, callback)
    },
  })
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
}
