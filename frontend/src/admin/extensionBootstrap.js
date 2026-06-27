import { generatedAdminExtensionModules } from 'virtual:bias-extension-import-map'
import {
  clearAdminRoutesForExtension,
  getAdminRoutes,
  registerAdminRoute,
  removeAdminRoute,
} from './registry/routes.js'
import { clearAdminRegistryExtensions } from './registry/shared.js'
import {
  createAdminExtensionApp,
  getAdminExtensionInitializers,
  resetAdminExtensionAppRuntime,
} from './extensionApp.js'
import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState.js'
import {
  handleExtensionRuntimeError,
  registerLoadedExtensionModule,
  unregisterLoadedExtensionModule,
} from '../common/extensionRuntime.js'
import {
  normalizeExtensionFrontendEntry,
  registerExtensionFrontendOutput,
  resolveExtensionRouteComponent,
  resolveExtensionRouteComponentKeys,
  withRuntimeApplication,
} from '../common/extensionRouteRuntime.js'
import { hasExtensionExtenders } from '../common/application.js'
import {
  registerRuntimeRouteDefinition,
  unregisterRuntimeRouteDefinition,
  unregisterRuntimeRoutesForExtension,
} from '../common/routeRegistry.js'

const loadedAdminExtensionIds = new Set()

const adminEntryModules = {
  ...generatedAdminExtensionModules,
}

const adminRouteComponents = {
  AdvancedPage: () => import('./views/AdvancedPage.vue'),
  AppearancePage: () => import('./views/AppearancePage.vue'),
  AuditLogsPage: () => import('./views/AuditLogsPage.vue'),
  BasicsPage: () => import('./views/BasicsPage.vue'),
  DashboardPage: () => import('./views/DashboardPage.vue'),
  DeveloperDocsPage: () => import('./views/DeveloperDocsPage.vue'),
  ExtensionDetailPage: () => import('./views/ExtensionDetailPage.vue'),
  ExtensionHostPage: () => import('./views/ExtensionHostPage.vue'),
  MailPage: () => import('./views/MailPage.vue'),
  PermissionsPage: () => import('./views/PermissionsPage.vue'),
}

export async function bootstrapEnabledAdminExtensions({
  app: application,
  extensions = [],
  router,
  runtime,
  entryModules = adminEntryModules,
  routeComponents = adminRouteComponents,
  registry = null,
} = {}) {
  let addedRouteCount = 0
  const resolvedRegistry = registry || await loadAdminRegistry()
  resetLoadedAdminExtensionsWhenRuntimeChanges(runtime, { router, app: application })
  const initializedApps = []

  for (const extension of extensions || []) {
    const extensionId = String(extension?.id || '').trim()
    const entryPath = normalizeAdminBootstrapEntry(extension?.frontend_admin_entry)
    if (!extensionId || !entryPath || loadedAdminExtensionIds.has(extensionId) || extension.enabled === false) {
      if (extensionId && extension?.enabled !== false && !loadedAdminExtensionIds.has(extensionId)) {
        const runtimeExtension = withRuntimeApplication(extension, application)
        registerExtensionFrontendOutput(application, extensionId, 'admin', runtimeExtension?.frontend_outputs?.admin)
        registerExtensionAdminRoutes(router, runtimeExtension, {
          app: application,
          components: routeComponents,
          importers: entryModules,
        })
        loadedAdminExtensionIds.add(extensionId)
      }
      continue
    }

    const runtimeExtension = withRuntimeApplication(extension, application)
    registerExtensionFrontendOutput(application, extensionId, 'admin', runtimeExtension?.frontend_outputs?.admin)
    registerExtensionAdminRoutes(router, runtimeExtension, {
      app: application,
      components: routeComponents,
      importers: entryModules,
    })

    const importer = entryModules[entryPath] || entryModules[extensionId]
    if (!importer) {
      continue
    }

    const module = await importer()
    const app = createAdminExtensionApp({
      app: application,
      extension: runtimeExtension,
      loadedExtensionIds: loadedAdminExtensionIds,
      registry: resolvedRegistry,
      router,
    })
    registerLoadedExtensionModule(extensionId, module, {
      app: application,
      extension: runtimeExtension,
      frontend: 'admin',
      entryPath,
    })
    await bootModuleExtenders(application, extensionId, module, app)
    initializedApps.push({ app, extensionId })
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

export function registerExtensionAdminRoutes(router, extension, { app = null, application = null, components = adminRouteComponents, importers = generatedAdminExtensionModules } = {}) {
  const runtimeApp = application || app || extension?.application || null
  const routes = Array.isArray(extension?.frontend_routes)
    ? extension.frontend_routes
    : []
  const registeredRoutes = []

  for (const route of routes) {
    if (String(route?.frontend || '').trim() !== 'admin') {
      continue
    }

    const name = String(route?.name || '').trim()
    if (!name) {
      continue
    }
    if (route?.removed) {
      removeAdminRoute(name)
      if (router && typeof router.removeRoute === 'function' && (!router.hasRoute || router.hasRoute(name))) {
        router.removeRoute(name)
      }
      unregisterRuntimeRouteDefinition(runtimeApp, name)
      registeredRoutes.push(name)
      continue
    }

    const path = String(route?.path || '').trim()
    const componentKey = String(route?.component || '').trim()
    if (!path || !componentKey) {
      continue
    }

    const component = resolveAdminRouteComponent(componentKey, extension, { components, importers })
    if (!component) {
      throw new Error(`找不到扩展后台路由组件: ${componentKey}`)
    }

    const normalizedRoute = {
      path,
      name,
      component,
      icon: route.icon || extension?.icon || 'fas fa-puzzle-piece',
      label: route.title || route.label || name,
      navDescription: route.description || '',
      navSection: route.nav_section || route.navSection || 'feature',
      navOrder: Number(route.order || route.nav_order || route.navOrder || 100),
      showInNavigation: route.show_in_navigation ?? route.showInNavigation ?? true,
      showInDashboardActions: route.show_in_dashboard_actions ?? route.showInDashboardActions ?? false,
      moduleId: route.module_id || extension.id,
      extensionId: extension.id,
      meta: {
        ...(route.meta || {}),
        extensionId: extension.id,
        moduleId: route.module_id || extension.id,
        requiresAuth: Boolean(route.requires_auth),
        title: route.title || undefined,
        description: route.description || undefined,
      },
    }
    registerAdminRoute(normalizedRoute)
    registerRuntimeRouteDefinition(runtimeApp, route, normalizedRoute, extension, 'admin')
    registeredRoutes.push(name)
  }

  return registeredRoutes
}

export function resolveAdminRouteComponent(componentKey, extension, { components = adminRouteComponents, importers = generatedAdminExtensionModules } = {}) {
  return resolveExtensionRouteComponent(componentKey, extension, {
    frontend: 'admin',
    components,
    importers,
    normalizeEntry: normalizeAdminBootstrapEntry,
  })
}

export function resolveAdminRouteComponentKeys(componentKey, extension = {}) {
  return resolveExtensionRouteComponentKeys(componentKey, extension, {
    frontend: 'admin',
    normalizeEntry: normalizeAdminBootstrapEntry,
  })
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

async function loadAdminRegistry() {
  return import('./registry.js')
}

export function resetLoadedAdminExtensions() {
  resetLoadedExtensions(loadedAdminExtensionIds, {
    onReset() {
      resetAdminExtensionRuntimeContributions()
    },
  })
}

export function resetLoadedAdminExtensionsWhenRuntimeChanges(runtime, { router, app } = {}) {
  return resetLoadedExtensionsWhenRuntimeChanges(loadedAdminExtensionIds, runtime, {
    onReset() {
      resetAdminExtensionRuntimeContributions('', { router, app })
    },
  })
}

export function getAdminInitializers() {
  return getAdminExtensionInitializers()
}

export function resetAdminExtensionRuntimeContributions(extensionId = '', { router, app } = {}) {
  removeAdminRuntimeRoutes(router, extensionId)
  clearAdminRoutesForExtension(extensionId)
  clearAdminRegistryExtensions(extensionId)
  unregisterLoadedExtensionModule(extensionId, { app })
  unregisterRuntimeRoutesForExtension(app, extensionId)
  resetAdminExtensionAppRuntime(extensionId, { app })
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
  const initializerGroups = new Set(items.map(item => item.app?.initializers).filter(Boolean))
  initializerGroups.add(getAdminExtensionInitializers())

  for (const initializers of initializerGroups) {
    await initializers.runWithAppResolver(extensionId => appsByExtensionId.get(extensionId), {
      onError(error, failingExtensionId) {
        handleExtensionRuntimeError(error, failingExtensionId, 'admin-initializer')
      },
    })
    for (const item of items) {
      initializers.clear(item.extensionId)
    }
  }
}

function normalizeAdminBootstrapEntry(entry) {
  return normalizeExtensionFrontendEntry(entry)
}
