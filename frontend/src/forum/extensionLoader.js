import api from '../api/index.js'
import { generatedForumExtensionModules } from 'virtual:bias-extension-import-map'
import { createRuntimeApplication, hasExtensionExtenders } from '../common/application.js'
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
import { resetResourceNormalizers } from '../common/resourceNormalizers.js'
import {
  normalizeExtensionFrontendEntry,
  registerExtensionFrontendOutput,
  resolveExtensionRouteComponent,
  resolveExtensionRouteComponentKeys,
  withRuntimeApplication,
} from '../common/extensionRouteRuntime.js'
import {
  registerRuntimeRouteDefinition,
  unregisterRuntimeRouteDefinition,
} from '../common/routeRegistry.js'

export {
  applyExtensionDocumentPayload,
  createForumExtensionApp,
  normalizeExtensionDocumentPayload,
  registerExtensionDocumentContent,
  registerExtensionTitleDriver,
}

const forumRouteComponents = {}

export function normalizeExtensionForumEntry(entry) {
  return normalizeExtensionFrontendEntry(entry)
}

export function registerExtensionForumRoutes(router, extension, { app = null, application = null, components = forumRouteComponents, importers = generatedForumExtensionModules } = {}) {
  if (!router || typeof router.addRoute !== 'function') {
    return []
  }

  const runtimeApp = application || app || extension?.application || null
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
      unregisterRuntimeRouteDefinition(runtimeApp, name)
      continue
    }
    if (!path || !componentKey) {
      continue
    }
    if (typeof router.hasRoute === 'function' && router.hasRoute(name)) {
      continue
    }

    const component = resolveForumRouteComponent(componentKey, extension, { components, importers })
    if (!component) {
      throw new Error(`找不到扩展前台路由组件: ${componentKey}`)
    }

    const normalizedRoute = {
      path,
      name,
      component,
      meta: {
        extensionId: extension.id,
        moduleId: route.module_id || extension.id,
        requiresAuth: Boolean(route.requires_auth),
        title: route.title || undefined,
        description: route.description || undefined,
        extensionDocument: {
          preloads: Array.isArray(route.preloads) ? route.preloads : [],
          documentAttributes: Array.isArray(route.document_attributes) ? route.document_attributes : [],
          headTags: Array.isArray(route.head_tags) ? route.head_tags : [],
        },
      },
    }
    router.addRoute(normalizedRoute)
    registerRuntimeRouteDefinition(runtimeApp, route, normalizedRoute, extension)
    registeredRoutes.push(name)
  }

  return registeredRoutes
}

export function resolveForumRouteComponent(componentKey, extension, { components = forumRouteComponents, importers = generatedForumExtensionModules } = {}) {
  return resolveExtensionRouteComponent(componentKey, extension, {
    frontend: 'forum',
    components,
    importers,
    normalizeEntry: normalizeExtensionForumEntry,
  })
}

export function resolveForumRouteComponentKeys(componentKey, extension = {}) {
  return resolveExtensionRouteComponentKeys(componentKey, extension, {
    frontend: 'forum',
    normalizeEntry: normalizeExtensionForumEntry,
  })
}

export async function loadExtensionForumEntryModule(entryPath, { importers = {} } = {}) {
  if (!entryPath) {
    return null
  }

  const importer = resolveExtensionImporter(entryPath, importers)
  if (!importer) {
    throw new Error(`找不到扩展前台入口: ${entryPath}`)
  }

  return importer()
}

export function validateForumExtensionModule(module, extensionId = '') {
  if (!module) {
    const suffix = extensionId ? ` (${extensionId})` : ''
    throw new Error(`扩展前台入口加载失败${suffix}`)
  }
}

export function validateCommonExtensionModule(module, extensionId = '') {
  if (!module) {
    const suffix = extensionId ? ` (${extensionId})` : ''
    throw new Error(`扩展通用入口加载失败${suffix}`)
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
  const extensionErrors = []
  for (const extension of extensions) {
    const extensionId = String(extension?.id || '').trim()
    if (!extensionId || loadedIds.has(extensionId)) {
      continue
    }

    try {
      const runtimeExtension = withRuntimeApplication(extension, application)
      registerExtensionFrontendOutput(application, extensionId, 'common', runtimeExtension?.frontend_outputs?.common)
      registerExtensionFrontendOutput(application, extensionId, 'forum', runtimeExtension?.frontend_outputs?.forum)

      const registeredRoutes = registerExtensionForumRoutes(router, runtimeExtension, {
        app: application,
        components: routeComponents || forumRouteComponents,
        importers,
      })
      let app = null
      const commonEntryPath = normalizeExtensionForumEntry(extension?.frontend_common_entry)
      if (commonEntryPath) {
        const commonModule = await loadExtensionForumEntryModule(commonEntryPath, { importers })
        validateCommonExtensionModule(commonModule, extensionId)
        app = createForumExtensionApp({
          app: application,
          forumStore,
          extension: runtimeExtension,
          loadedExtensionIds: loadedIds,
          registry,
          router,
          registeredRoutes,
        })
        registerLoadedExtensionModule(extensionId, commonModule, {
          app: application,
          extension: runtimeExtension,
          frontend: 'common',
          entryPath: commonEntryPath,
        })
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
        extension: runtimeExtension,
        loadedExtensionIds: loadedIds,
        registry,
        router,
        registeredRoutes,
      })
      registerLoadedExtensionModule(extensionId, module, {
        app: application,
        extension: runtimeExtension,
        frontend: 'forum',
        entryPath,
      })
      await bootModuleExtenders(application, extensionId, module, app)
      initializedApps.push({ app, extensionId })
      loadedIds.add(extensionId)
    } catch (error) {
      extensionErrors.push({ extensionId, error })
      handleExtensionRuntimeError(error, extensionId, 'forum-entry')
    }
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
    extensionErrors,
    loadedExtensionIds: loadedIds,
  }
}

function resolveExtensionImporter(entryPath, importers) {
  const normalized = String(entryPath || '').replace(/\\/g, '/').trim()
  if (!normalized) return null

  const direct = importers[normalized]
  if (typeof direct === 'function') return direct

  const candidates = buildExtensionImporterCandidates(normalized)
  for (const candidate of candidates) {
    const importer = importers[candidate]
    if (typeof importer === 'function') {
      return importer
    }
  }

  return null
}

function buildExtensionImporterCandidates(entryPath) {
  const candidates = new Set()
  const normalized = String(entryPath || '').replace(/\\/g, '/').trim()
  if (!normalized) return candidates

  candidates.add(normalized)
  const withoutParentPrefixes = normalized.replace(/^(\.\.\/)+/, '')
  if (withoutParentPrefixes) {
    candidates.add(withoutParentPrefixes)
    candidates.add(`../${withoutParentPrefixes}`)
    candidates.add(`../../${withoutParentPrefixes}`)
    candidates.add(`../../../${withoutParentPrefixes}`)
  }
  if (normalized.startsWith('../')) {
    candidates.add(normalized.replace(/^\.\.\//, './'))
  }

  return candidates
}

async function bootModuleExtenders(application, extensionId, module, extensionApp) {
  if (!application || !hasExtensionExtenders(module)) {
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
  initializerGroups.add(getForumExtensionInitializers())

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
  resetResourceNormalizers(extensionId)
  if (extensionId) {
    clearExtensionDocumentRuntimeForExtension(extensionId)
  } else {
    clearExtensionDocumentRuntime()
  }
  unregisterLoadedExtensionModule(extensionId, { app })
  resetForumExtensionAppRuntime(extensionId, { app })
}
