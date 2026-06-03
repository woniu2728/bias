import {
  createExtensionInitializers,
  createExtensionPatcher,
  runWithExtensionScope,
} from '../common/extensionRuntime.js'
import { createExtensionAppApi } from '../common/extensionAppApi.js'

const adminInitializers = createExtensionInitializers()
const adminPatcher = createExtensionPatcher()

export function createAdminExtensionApp({
  extension,
  loadedExtensionIds,
  registry = {},
  router,
} = {}) {
  const appApi = createExtensionAppApi({
    api: registry.adminApi,
    extension,
    store: registry,
  })
  return Object.freeze({
    ...appApi,
    api: registry.adminApi,
    extension,
    initializers: adminInitializers,
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

export function resetAdminExtensionAppRuntime(extensionId = '') {
  adminInitializers.clear(extensionId)
  adminPatcher.reset(extensionId)
}
