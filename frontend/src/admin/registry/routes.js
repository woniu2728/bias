const adminRoutes = []

import { getCurrentExtensionId } from '../../common/extensionRuntime.js'

function upsertByPath(target, value) {
  const existingIndex = target.findIndex(item => item.path === value.path)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function matchesRoutePath(routePath, currentPath) {
  if (routePath === currentPath) {
    return true
  }

  const pattern = String(routePath || '')
    .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    .replace(/:([A-Za-z0-9_]+)/g, '[^/]+')

  if (!pattern) {
    return false
  }

  return new RegExp(`^${pattern}$`).test(currentPath)
}

export function registerAdminRoute(route) {
  const extensionId = String(route?.extensionId || route?.extension_id || getCurrentExtensionId() || '').trim()
  const normalizedRoute = {
    navSection: 'feature',
    navOrder: 100,
    showInNavigation: true,
    showInDashboardActions: false,
    dashboardActionOrder: null,
    dashboardActionLabel: '',
    navDescription: '',
    navBadge: '',
    ...route,
    ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
  }

  return upsertByPath(adminRoutes, normalizedRoute)
}

export function clearAdminRoutesForExtension(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (let index = adminRoutes.length - 1; index >= 0; index -= 1) {
    const routeExtensionId = String(adminRoutes[index]?.extensionId || adminRoutes[index]?.extension_id || '').trim()
    if (!routeExtensionId) {
      continue
    }
    if (!normalizedExtensionId || routeExtensionId === normalizedExtensionId) {
      adminRoutes.splice(index, 1)
    }
  }
}

export function removeAdminRoute(name) {
  const normalizedName = String(name || '').trim()
  if (!normalizedName) {
    return false
  }
  let removed = false
  for (let index = adminRoutes.length - 1; index >= 0; index -= 1) {
    if (String(adminRoutes[index]?.name || '').trim() === normalizedName) {
      adminRoutes.splice(index, 1)
      removed = true
    }
  }
  return removed
}

function sortAdminRoutes(routes) {
  return [...routes].sort((left, right) => {
    if (left.path === '/admin') return -1
    if (right.path === '/admin') return 1
    return (left.navOrder || 100) - (right.navOrder || 100)
  })
}

function isRouteVisible(route, options = {}) {
  const isModuleEnabled = options.isModuleEnabled || (() => true)
  return isModuleEnabled(route.moduleId || 'core')
}

export function getAdminRoutes(options = {}) {
  return sortAdminRoutes(
    adminRoutes.filter(route => isRouteVisible(route, options))
  )
}

export function findAdminRouteByPath(path, options = {}) {
  return getAdminRoutes(options).find(route => matchesRoutePath(route.path, path))
}

export function getAdminNavSections(options = {}) {
  const sections = {
    core: { key: 'core', title: '核心', items: [] },
    feature: { key: 'feature', title: '功能', items: [] },
    extensions: { key: 'extensions', title: '扩展', items: [] },
  }

  for (const route of getAdminRoutes(options)) {
    if (!route.showInNavigation) {
      continue
    }

    const routeExtensionId = String(route.extensionId || route.extension_id || '').trim()
    const sectionKey = routeExtensionId && route.navSection !== 'core' ? 'extensions' : route.navSection
    const section = sections[sectionKey] || sections.feature
    section.items.push({
      path: route.path,
      icon: route.icon,
      label: route.label,
      description: route.navDescription || '',
      badge: route.navBadge || '',
      moduleId: route.moduleId || 'core',
      navOrder: route.navOrder || 100
    })
  }

  return Object.values(sections)
    .map(section => ({
      ...section,
      items: section.items.sort((left, right) => left.navOrder - right.navOrder)
    }))
    .filter(section => section.items.length > 0)
}

export function getAdminDashboardActions(options = {}) {
  return getAdminRoutes(options)
    .filter(route => route.showInDashboardActions && !route.redirect)
    .sort((left, right) => {
      const leftOrder = left.dashboardActionOrder ?? left.navOrder ?? 100
      const rightOrder = right.dashboardActionOrder ?? right.navOrder ?? 100
      return leftOrder - rightOrder
    })
    .map(route => ({
      key: route.name || route.path,
      to: route.path,
      icon: route.icon,
      label: route.dashboardActionLabel || route.label,
      description: route.navDescription || '',
      moduleId: route.moduleId || 'core',
    }))
}
