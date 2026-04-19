export const coreItems = [
  { path: '/admin', icon: 'fas fa-chart-bar', label: '仪表盘' },
  { path: '/admin/basics', icon: 'fas fa-pencil-alt', label: '基础设置' },
  { path: '/admin/permissions', icon: 'fas fa-key', label: '权限管理' },
  { path: '/admin/appearance', icon: 'fas fa-paint-brush', label: '外观设置' },
  { path: '/admin/users', icon: 'fas fa-users', label: '用户管理' },
]

export const featureItems = [
  { path: '/admin/approval', icon: 'fas fa-user-check', label: '审核队列' },
  { path: '/admin/flags', icon: 'fas fa-flag', label: '举报管理' },
  { path: '/admin/tags', icon: 'fas fa-tags', label: '标签管理' },
  { path: '/admin/mail', icon: 'fas fa-envelope', label: '邮件设置' },
  { path: '/admin/advanced', icon: 'fas fa-cog', label: '高级设置' },
]

export const adminNavSections = [
  { key: 'core', title: '核心', items: coreItems },
  { key: 'feature', title: '功能', items: featureItems },
]

export function isAdminPathActive(currentPath, targetPath) {
  if (targetPath === '/admin') {
    return currentPath === '/admin'
  }

  return currentPath.startsWith(targetPath)
}

export function getAdminRouteMeta(currentPath) {
  for (const section of adminNavSections) {
    for (const item of section.items) {
      if (isAdminPathActive(currentPath, item.path)) {
        return item
      }
    }
  }

  return coreItems[0]
}
