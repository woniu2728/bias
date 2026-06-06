import api from '../api/index.js'
import { createRuntimeApplication } from '../common/application.js'
import {
  applyExtensionDocumentPayload,
  clearExtensionDocumentRuntime,
  clearExtensionDocumentRuntimeForExtension,
  normalizeExtensionDocumentPayload,
  registerExtensionDocumentContent,
  registerExtensionTitleDriver,
} from './documentRuntime.js'
import {
  createForumExtensionApp,
  getForumExtensionInitializers,
  resetForumExtensionAppRuntime,
} from './extensionApp.js'
import { clearForumRegistryExtensions } from './frontendRegistry.js'
import {
  handleExtensionRuntimeError,
  registerLoadedExtensionModule,
  unregisterLoadedExtensionModule,
} from '../common/extensionRuntime.js'

export {
  applyExtensionDocumentPayload,
  createForumExtensionApp,
  normalizeExtensionDocumentPayload,
  registerExtensionDocumentContent,
  registerExtensionTitleDriver,
}

const forumRouteComponents = {
  DiscussionListView: () => import('../views/DiscussionListView.vue'),
  NotificationView: () => import('../views/NotificationView.vue'),
  TagsView: () => import('../views/TagsView.vue'),
}

export function normalizeExtensionForumEntry(entry) {
  const value = String(entry || '').trim()
  if (!value) {
    return ''
  }

  const normalized = value.startsWith('extensions/')
    ? `../../../${value}`
    : value

  return normalized.replace(/\\/g, '/')
}

export function registerExtensionForumRoutes(router, extension, { components = forumRouteComponents } = {}) {
  if (!router || typeof router.addRoute !== 'function') {
    return []
  }

  const routes = Array.isArray(extension?.frontend_routes)
    ? extension.frontend_routes
    : []

  const registeredRoutes = []
  for (const route of routes) {
    if (String(route?.frontend || 'forum').trim() !== 'forum') {
      continue
    }

    const path = String(route?.path || '').trim()
    const name = String(route?.name || '').trim()
    const componentKey = String(route?.component || '').trim()
    if (!name) {
      continue
    }
    if (route?.removed) {
      if (typeof router.removeRoute === 'function' && typeof router.hasRoute === 'function' && router.hasRoute(name)) {
        router.removeRoute(name)
        registeredRoutes.push(name)
      }
      continue
    }
    if (!path || !componentKey) {
      continue
    }
    if (typeof router.hasRoute === 'function' && router.hasRoute(name)) {
      continue
    }

    const component = components[componentKey]
    if (!component) {
      throw new Error(`找不到扩展前台路由组件: ${componentKey}`)
    }

    router.addRoute({
      path,
      name,
      component,
      meta: {
        extensionId: extension.id,
        moduleId: route.module_id || extension.id,
        requiresAuth: Boolean(route.requires_auth),
        title: route.title || undefined,
        description: route.description || undefined,
      },
    })
    registeredRoutes.push(name)
  }

  return registeredRoutes
}

export async function loadExtensionForumEntryModule(entryPath, { importers = {} } = {}) {
  if (!entryPath) {
    return null
  }

  const importer = importers[entryPath]
  if (!importer) {
    throw new Error(`找不到扩展前台入口: ${entryPath}`)
  }

  return importer()
}

export function validateForumExtensionModule(module, extensionId = '') {
  if (!module || !module.extend) {
    const suffix = extensionId ? ` (${extensionId})` : ''
    throw new Error(`扩展前台入口缺少 extend 导出${suffix}`)
  }
}

export function validateCommonExtensionModule(module, extensionId = '') {
  if (!module || !module.extend) {
    const suffix = extensionId ? ` (${extensionId})` : ''
    throw new Error(`扩展通用入口缺少 extend 导出${suffix}`)
  }
}

export async function loadEnabledForumExtensions({
  forumStore,
  app: providedApplication,
  importers = {},
  router,
  routeComponents,
  registry = {},
  fetchPayload,
  loadedExtensionIds,
} = {}) {
  const application = providedApplication || createRuntimeApplication({ kind: 'forum' })
  const payload = typeof fetchPayload === 'function'
    ? await fetchPayload()
    : await api.get('/forum')

  const extensionDocument = applyExtensionDocumentPayload(payload)

  const extensions = Array.isArray(payload?.enabled_extensions)
    ? payload.enabled_extensions
    : []

  const loadedIds = loadedExtensionIds || new Set()
  resetLoadedExtensionsWhenRuntimeChanges(loadedIds, payload?.extension_runtime, {
    onReset() {
      resetForumExtensionRuntimeContributions('', { app: application })
    },
  })

  const initializedApps = []
  for (const extension of extensions) {
    const extensionId = String(extension?.id || '').trim()
    if (!extensionId || loadedIds.has(extensionId)) {
      continue
    }

    const registeredRoutes = registerExtensionForumRoutes(router, extension, { components: routeComponents || forumRouteComponents })
    let app = null
    const commonEntryPath = normalizeExtensionForumEntry(extension?.frontend_common_entry)
    if (commonEntryPath) {
      const commonModule = await loadExtensionForumEntryModule(commonEntryPath, { importers })
      validateCommonExtensionModule(commonModule, extensionId)
      app = createForumExtensionApp({
        app: application,
        forumStore,
        extension,
        loadedExtensionIds: loadedIds,
        registry,
        router,
        registeredRoutes,
      })
      registerLoadedExtensionModule(extensionId, commonModule, {
        app: application,
        extension,
        frontend: 'common',
        entryPath: commonEntryPath,
      })
      registerExtensionFrontendOutput(application, extensionId, 'common', extension?.frontend_outputs?.common)
      await bootModuleExtenders(application, extensionId, commonModule, app)
    }

    const entryPath = normalizeExtensionForumEntry(extension?.frontend_forum_entry)
    if (!entryPath) {
      if (app) {
        initializedApps.push({ app, extensionId })
      }
      loadedIds.add(extensionId)
      continue
    }

    const module = await loadExtensionForumEntryModule(entryPath, { importers })
    validateForumExtensionModule(module, extensionId)
    app = createForumExtensionApp({
      app: application,
      forumStore,
      extension,
      loadedExtensionIds: loadedIds,
      registry,
      router,
      registeredRoutes,
    })
    registerLoadedExtensionModule(extensionId, module, {
      app: application,
      extension,
      frontend: 'forum',
      entryPath,
    })
    registerExtensionFrontendOutput(application, extensionId, 'forum', extension?.frontend_outputs?.forum)
    await bootModuleExtenders(application, extensionId, module, app)
    initializedApps.push({ app, extensionId })
    loadedIds.add(extensionId)
  }

  if (initializedApps.length) {
    await runForumExtensionInitializers(initializedApps)
  }

  if (forumStore && typeof forumStore.applyPublicSettings === 'function') {
    forumStore.applyPublicSettings(payload)
  }

  return {
    payload,
    extensionDocument,
    loadedExtensionIds: loadedIds,
  }
}

function registerExtensionFrontendOutput(application, extensionId, frontend, output) {
  const registry = application?.exportRegistry
  if (!registry || !output || typeof registry.registerViteOutput !== 'function') {
    return []
  }
  return registry.registerViteOutput(extensionId, frontend, output, {
    baseUrl: resolveFrontendAssetsBaseUrl(),
  })
}

function resolveFrontendAssetsBaseUrl() {
  return globalThis.bias?.frontendAssetsBaseUrl || '/static/frontend'
}

async function bootModuleExtenders(application, extensionId, module, extensionApp) {
  if (!application || !module?.extend) {
    return
  }
  await application.bootExtensions({
    [extensionId]: module,
  }, {
    createExtensionApp: () => extensionApp,
    onError(error, failingExtensionId) {
      handleExtensionRuntimeError(error, failingExtensionId, 'extender')
    },
  })
}

export function getForumInitializers() {
  return getForumExtensionInitializers()
}

async function runForumExtensionInitializers(items) {
  const appsByExtensionId = new Map(items.map(item => [item.extensionId, item.app]))
  const initializerGroups = new Set(items.map(item => item.app?.initializers).filter(Boolean))
  if (!initializerGroups.size) {
    initializerGroups.add(getForumExtensionInitializers())
  }

  for (const initializers of initializerGroups) {
    await initializers.runWithAppResolver(extensionId => appsByExtensionId.get(extensionId), {
      onError(error, failingExtensionId) {
        handleExtensionRuntimeError(error, failingExtensionId, 'initializer')
      },
    })
    for (const item of items) {
      initializers.clear(item.extensionId)
    }
  }
}

export function resetLoadedExtensionsWhenRuntimeChanges(loadedIds, runtime, { onReset } = {}) {
  if (!loadedIds || typeof loadedIds.clear !== 'function') {
    return false
  }
  const stamp = String(runtime?.stamp || '')
  const previousStamp = loadedIds.__biasRuntimeStamp || ''
  if (!stamp) {
    return false
  }
  if (previousStamp && previousStamp !== stamp) {
    loadedIds.clear()
    if (typeof onReset === 'function') {
      onReset()
    }
  }
  loadedIds.__biasRuntimeStamp = stamp
  return previousStamp !== stamp
}

export function resetForumExtensionRuntimeContributions(extensionId = '', { app } = {}) {
  clearForumRegistryExtensions(extensionId)
  if (extensionId) {
    clearExtensionDocumentRuntimeForExtension(extensionId)
  } else {
    clearExtensionDocumentRuntime()
  }
  unregisterLoadedExtensionModule(extensionId, { app })
  resetForumExtensionAppRuntime(extensionId, { app })
}
