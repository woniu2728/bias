export function registerRuntimeRouteDefinition(app, route, normalizedRoute, extension, frontend = 'forum') {
  if (!app || !route?.name) {
    return
  }
  app.routes ||= { definitions: Object.create(null), helpers: Object.create(null) }
  app.routes.definitions ||= Object.create(null)
  app.routes.definitions[route.name] = {
    path: normalizedRoute.path,
    name: normalizedRoute.name,
    component: normalizedRoute.component,
    frontend: String(route.frontend || frontend || 'forum').trim() || String(frontend || 'forum'),
    extensionId: extension?.id,
    extension_id: extension?.id,
    moduleId: route.module_id || extension?.id,
    module_id: route.module_id || extension?.id,
    title: route.title || route.label || '',
    description: route.description || '',
    requiresAuth: Boolean(route.requires_auth),
    requires_auth: Boolean(route.requires_auth),
    order: Number.isFinite(Number(route.order)) ? Number(route.order) : 100,
    meta: normalizedRoute.meta || {},
  }
}

export function unregisterRuntimeRouteDefinition(app, name) {
  if (!app?.routes?.definitions || !name) {
    return
  }
  delete app.routes.definitions[name]
}

export function unregisterRuntimeRoutesForExtension(app, extensionId = '') {
  if (!app?.routes?.definitions) {
    return
  }
  const normalizedExtensionId = String(extensionId || '').trim()
  for (const [name, route] of Object.entries(app.routes.definitions)) {
    const routeExtensionId = String(route?.extensionId || route?.extension_id || '').trim()
    if (routeExtensionId && (!normalizedExtensionId || routeExtensionId === normalizedExtensionId)) {
      delete app.routes.definitions[name]
    }
  }
}
