import { getAdminNavSections as getRegisteredAdminNavSections } from './registry'
import { useAdminRegistryStore } from '../stores/adminRegistry'

export function isAdminPathActive(currentPath, targetPath) {
  if (targetPath === '/admin') {
    return currentPath === '/admin'
  }

  return currentPath.startsWith(targetPath)
}

export function getAdminNavSections() {
  const adminRegistryStore = useAdminRegistryStore()
  return getRegisteredAdminNavSections({
    isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
  })
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
