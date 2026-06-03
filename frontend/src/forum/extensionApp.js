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
    store: forumStore,
  })
  return Object.freeze({
    ...appApi,
    api,
    extension,
    initializers: forumInitializers,
    extend: forumPatcher.extend,
    override: forumPatcher.override,
    resetPatches: forumPatcher.reset,
    forumStore,
    loadedExtensionIds,
    registeredRoutes,
    router,
    registry,
    documentRuntime: {
      registerTitleDriver: registerExtensionTitleDriver,
      registerContent: registerExtensionDocumentContent,
    },
    runWithExtensionScope(callback) {
      return runWithExtensionScope(extension?.id, callback)
    },
  })
}

export function getForumExtensionInitializers() {
  return forumInitializers
}

export function resetForumExtensionAppRuntime(extensionId = '') {
  forumInitializers.clear(extensionId)
  forumPatcher.reset(extensionId)
}
