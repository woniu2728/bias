import { generatedAdminExtensionModules } from '../generated/extensionImportMap'
import * as adminRegistry from './registry'
import {
  clearAdminRoutesForExtension,
  getAdminRoutes,
} from './registry/routes'
import {
  createAdminExtensionApp,
  getAdminExtensionInitializers,
  resetAdminExtensionAppRuntime,
} from './extensionApp'
import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState'
import {
  handleExtensionRuntimeError,
  runWithExtensionScope,
} from '../common/extensionRuntime'

const loadedAdminExtensionIds = new Set()

const adminEntryModules = {
  ...import.meta.glob('../../../extensions/*/frontend/admin/index.js'),
  ...generatedAdminExtensionModules,
}

export async function bootstrapEnabledAdminExtensions({ extensions = [], router, runtime } = {}) {
  let addedRouteCount = 0
  resetLoadedAdminExtensionsWhenRuntimeChanges(runtime, { router })
  const initializedApps = []

  for (const extension of extensions || []) {
    const extensionId = String(extension?.id || '').trim()
    const entryPath = normalizeAdminBootstrapEntry(extension?.frontend_admin_entry)
    if (!extensionId || !entryPath || loadedAdminExtensionIds.has(extensionId) || extension.enabled === false) {
      continue
    }

    const importer = adminEntryModules[entryPath] || adminEntryModules[extensionId]
    if (!importer) {
      continue
    }

    const module = await importer()
    if (typeof module?.bootAdminExtension === 'function') {
      const app = createAdminExtensionApp({
        extension,
        loadedExtensionIds: loadedAdminExtensionIds,
        registry: adminRegistry,
        router,
      })
      await runWithExtensionScope(extensionId, () => module.bootAdminExtension({
        app,
        api: app.api,
        registry: app.registry,
        extension,
        router,
      }))
      initializedApps.push({ app, extensionId })
    }
    loadedAdminExtensionIds.add(extensionId)
  }

  if (initializedApps.length) {
    await runAdminExtensionInitializers(initializedApps)
  }

  if (router && typeof router.addRoute === 'function') {
    for (const route of getAdminRoutes()) {
      if (!route?.name || router.hasRoute(route.name)) {
        continue
      }
      router.addRoute({
        path: route.path,
        name: route.name,
        component: route.component,
        redirect: route.redirect,
        meta: {
          ...(route.meta || {}),
          ...(route.extensionId ? { extensionId: route.extensionId } : {}),
        },
      })
      addedRouteCount += 1
    }
  }

  return { addedRouteCount }
}

export function resetLoadedAdminExtensions() {
  resetLoadedExtensions(loadedAdminExtensionIds, {
    onReset() {
      resetAdminExtensionRuntimeContributions()
    },
  })
}

export function resetLoadedAdminExtensionsWhenRuntimeChanges(runtime, { router } = {}) {
  return resetLoadedExtensionsWhenRuntimeChanges(loadedAdminExtensionIds, runtime, {
    onReset() {
      resetAdminExtensionRuntimeContributions('', { router })
    },
  })
}

export function getAdminInitializers() {
  return getAdminExtensionInitializers()
}

export function resetAdminExtensionRuntimeContributions(extensionId = '', { router } = {}) {
  removeAdminRuntimeRoutes(router, extensionId)
  clearAdminRoutesForExtension(extensionId)
  resetAdminExtensionAppRuntime(extensionId)
}

function removeAdminRuntimeRoutes(router, extensionId = '') {
  if (!router || typeof router.getRoutes !== 'function' || typeof router.removeRoute !== 'function') {
    return
  }
  const normalizedExtensionId = String(extensionId || '').trim()
  for (const route of router.getRoutes()) {
    const routeExtensionId = String(route?.meta?.extensionId || route?.meta?.extension_id || '').trim()
    if (!routeExtensionId) {
      continue
    }
    if (!normalizedExtensionId || routeExtensionId === normalizedExtensionId) {
      router.removeRoute(route.name)
    }
  }
}

async function runAdminExtensionInitializers(items) {
  const appsByExtensionId = new Map(items.map(item => [item.extensionId, item.app]))
  const initializers = getAdminExtensionInitializers()
  await initializers.runWithAppResolver(extensionId => appsByExtensionId.get(extensionId), {
    onError(error, failingExtensionId) {
      handleExtensionRuntimeError(error, failingExtensionId, 'admin-initializer')
    },
  })
  for (const item of items) {
    initializers.clear(item.extensionId)
  }
}

function normalizeAdminBootstrapEntry(entry) {
  const value = String(entry || '').trim()
  if (!value) {
    return ''
  }
  return value.startsWith('extensions/')
    ? `../../../${value}`.replace(/\\/g, '/')
    : value.replace(/\\/g, '/')
}
