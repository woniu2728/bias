const adminRoutes = []

function buildAdminHashPath(path = '') {
  const normalizedPath = String(path || '').trim()
  if (!normalizedPath) return '#/'
  return `#${normalizedPath}`
}

function upsertByPath(target, value) {
  const existingIndex = target.findIndex(item => item.path === value.path)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

export function registerAdminRoute(route) {
  const normalizedRoute = {
    navSection: 'feature',
    navOrder: 100,
    showInNavigation: true,
    showInDashboardActions: false,
    dashboardActionOrder: null,
    dashboardActionLabel: '',
    navDescription: '',
    navBadge: '',
    ...route
  }

  return upsertByPath(adminRoutes, normalizedRoute)
}

export function getAdminRoutes() {
  return [...adminRoutes].sort((left, right) => {
    if (left.path === '/admin') return -1
    if (right.path === '/admin') return 1
    return (left.navOrder || 100) - (right.navOrder || 100)
  })
}

export function getAdminNavSections() {
  const sections = {
    core: { key: 'core', title: '核心', items: [] },
    feature: { key: 'feature', title: '功能', items: [] }
  }

  for (const route of getAdminRoutes()) {
    if (!route.showInNavigation) {
      continue
    }

    const section = sections[route.navSection] || sections.feature
    section.items.push({
      path: route.path,
      hashPath: buildAdminHashPath(route.path),
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

export function getAdminDashboardActions() {
  return getAdminRoutes()
    .filter(route => route.showInDashboardActions)
    .sort((left, right) => {
      const leftOrder = left.dashboardActionOrder ?? left.navOrder ?? 100
      const rightOrder = right.dashboardActionOrder ?? right.navOrder ?? 100
      return leftOrder - rightOrder
    })
    .map(route => ({
      key: route.name || route.path,
      to: buildAdminHashPath(route.path),
      icon: route.icon,
      label: route.dashboardActionLabel || route.label,
      description: route.navDescription || '',
      moduleId: route.moduleId || 'core',
    }))
}
