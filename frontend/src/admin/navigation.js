import { getAdminRoutes } from './registry/routes.js'
import { useAdminRegistryStore } from '../stores/adminRegistry.js'

export function isAdminPathActive(currentPath, targetPath) {
  if (targetPath === '/admin') {
    return currentPath === '/admin'
  }

  return currentPath.startsWith(targetPath)
}

export function getAdminNavSections() {
  const adminRegistryStore = useAdminRegistryStore()
  const routes = getAdminRoutes({
    isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
  })
  const visibleRoutes = routes.filter(route => route.showInNavigation !== false)
  const coreModuleIds = new Set(
    visibleRoutes
      .filter(route => !route.redirect && !isExtensionOwnedRoute(route))
      .map(route => String(route.moduleId || 'core').trim())
      .filter(Boolean)
  )
  const firstClassAdminExtensionIds = new Set(
    visibleRoutes
      .filter(route => !route.redirect && isExtensionOwnedRoute(route) && !isExtensionDetailRoute(route))
      .map(route => String(route.extensionId || route.extension_id || '').trim())
      .filter(Boolean)
  )
  const coreItems = visibleRoutes
    .filter((route) => {
      if (route.path.startsWith('/admin/extensions/')) {
        return false
      }
      if (route.redirect) {
        return false
      }
      return true
    })
    .map(route => ({
      path: route.path,
      icon: route.icon,
      label: route.label,
      description: route.navDescription || '',
      badge: route.navBadge || '',
      moduleId: route.moduleId || 'core',
      navOrder: route.navOrder || 100,
    }))

  const filteredSections = coreItems.length ? [{
    key: 'core',
    title: '核心配置',
    items: coreItems,
  }] : []

  const extensionItems = (adminRegistryStore.extensions || [])
    .map(section => ({
      ...section,
    }))
    .filter(item => item?.id && item.id !== 'core')
    .filter(item => item?.product_visible !== false)
    .filter(item => !firstClassAdminExtensionIds.has(String(item.id || '').trim()))
    .filter(item => !coreModuleIds.has(String(item.id || '').trim()))
    .map(item => ({
      path: `/admin/extensions/${item.id}`,
      icon: item.icon || 'fas fa-puzzle-piece',
      label: item.name || item.id,
      description: item.description || '',
      badge: item.enabled === false ? '' : ' ',
      moduleId: '',
      navOrder: Number(item.display_order || item.order || 1000),
      activeWhen: item.active_when || '',
      style: buildExtensionIconStyle(item),
    }))
    .sort((left, right) => {
      if (left.navOrder !== right.navOrder) {
        return left.navOrder - right.navOrder
      }
      return String(left.label || '').localeCompare(String(right.label || ''), 'zh-CN')
    })

  if (extensionItems.length) {
    filteredSections.push({
      key: 'extensions',
      title: '扩展',
      items: extensionItems,
    })
  }

  return filteredSections
}

function buildExtensionIconStyle(extension) {
  const palette = [
    ['#f28c28', '#fff3e5'],
    ['#31a36b', '#e9f7f0'],
    ['#d84fa0', '#fdebf5'],
    ['#4f80c8', '#edf4ff'],
    ['#8b63d8', '#f2edff'],
    ['#d9a321', '#fff7df'],
    ['#2f9aa0', '#e8f7f8'],
    ['#6b778d', '#eef2f7'],
  ]
  const key = String(extension?.id || extension?.name || '')
  const index = [...key].reduce((total, char) => total + char.charCodeAt(0), 0) % palette.length
  const [color, background] = palette[index]
  return {
    '--admin-extension-icon-color': color,
    '--admin-extension-icon-bg': background,
  }
}

function isExtensionOwnedRoute(route) {
  return Boolean(String(route?.extensionId || route?.extension_id || '').trim())
}

function isExtensionDetailRoute(route) {
  return String(route?.path || '').startsWith('/admin/extensions/')
}

export function getAdminRouteMeta(currentPath) {
  const sections = getAdminNavSections()

  for (const section of sections) {
    for (const item of section.items) {
      if (isAdminPathActive(currentPath, item.path)) {
        return item
      }
    }
  }

  return sections[0]?.items[0] || { path: '/admin', icon: 'fas fa-chart-bar', label: '仪表盘' }
}
