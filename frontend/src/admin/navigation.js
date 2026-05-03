import { getAdminNavSections as getRegisteredAdminNavSections } from './registry'

export function isAdminPathActive(currentPath, targetPath) {
  if (targetPath === '/admin') {
    return currentPath === '/admin'
  }

  return currentPath.startsWith(targetPath)
}

export function getAdminNavSections() {
  return getRegisteredAdminNavSections()
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
