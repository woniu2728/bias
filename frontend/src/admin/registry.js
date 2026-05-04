import DashboardPage from './views/DashboardPage.vue'
import ModulesPage from './views/ModulesPage.vue'
import BasicsPage from './views/BasicsPage.vue'
import PermissionsPage from './views/PermissionsPage.vue'
import UsersPage from './views/UsersPage.vue'
import FlagsPage from './views/FlagsPage.vue'
import ApprovalQueuePage from './views/ApprovalQueuePage.vue'
import AuditLogsPage from './views/AuditLogsPage.vue'
import AppearancePage from './views/AppearancePage.vue'
import TagsPage from './views/TagsPage.vue'
import MailPage from './views/MailPage.vue'
import AdvancedPage from './views/AdvancedPage.vue'

const adminRoutes = []

export function registerAdminRoute(route) {
  const normalizedRoute = {
    navSection: 'feature',
    navOrder: 100,
    showInNavigation: true,
    navDescription: '',
    navBadge: '',
    ...route
  }

  const existingIndex = adminRoutes.findIndex(item => item.path === normalizedRoute.path)
  if (existingIndex >= 0) {
    adminRoutes.splice(existingIndex, 1, normalizedRoute)
    return normalizedRoute
  }

  adminRoutes.push(normalizedRoute)
  return normalizedRoute
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

registerAdminRoute({
  path: '/admin',
  name: 'admin-dashboard',
  component: DashboardPage,
  icon: 'fas fa-chart-bar',
  label: '仪表盘',
  navDescription: '查看论坛运行状态、模块概况和系统入口。',
  navSection: 'core',
  navOrder: 10,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/modules',
  name: 'admin-modules',
  component: ModulesPage,
  icon: 'fas fa-cubes',
  label: '模块中心',
  navDescription: '查看内置模块、扩展能力和注册快照。',
  navSection: 'core',
  navOrder: 20,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/basics',
  name: 'admin-basics',
  component: BasicsPage,
  icon: 'fas fa-pencil-alt',
  label: '基础设置',
  navDescription: '维护论坛标题、公告和基础信息。',
  navSection: 'core',
  navOrder: 30,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/permissions',
  name: 'admin-permissions',
  component: PermissionsPage,
  icon: 'fas fa-key',
  label: '权限管理',
  navDescription: '管理用户组和访问权限矩阵。',
  navSection: 'core',
  navOrder: 40,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/appearance',
  name: 'admin-appearance',
  component: AppearancePage,
  icon: 'fas fa-paint-brush',
  label: '外观设置',
  navDescription: '调整主题、Logo 和界面外观。',
  navSection: 'core',
  navOrder: 50,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/users',
  name: 'admin-users',
  component: UsersPage,
  icon: 'fas fa-users',
  label: '用户管理',
  navDescription: '查看用户资料、分组和封禁状态。',
  navSection: 'core',
  navOrder: 60,
  moduleId: 'users'
})

registerAdminRoute({
  path: '/admin/approval',
  name: 'admin-approval',
  component: ApprovalQueuePage,
  icon: 'fas fa-user-check',
  label: '审核队列',
  navDescription: '集中处理待审核讨论和回复。',
  navSection: 'feature',
  navOrder: 110,
  moduleId: 'approval'
})

registerAdminRoute({
  path: '/admin/flags',
  name: 'admin-flags',
  component: FlagsPage,
  icon: 'fas fa-flag',
  label: '举报管理',
  navDescription: '查看和处理社区举报内容。',
  navSection: 'feature',
  navOrder: 120,
  moduleId: 'flags'
})

registerAdminRoute({
  path: '/admin/audit-logs',
  name: 'admin-audit-logs',
  component: AuditLogsPage,
  icon: 'fas fa-clipboard-list',
  label: '审计日志',
  navDescription: '追踪后台关键操作记录。',
  navSection: 'feature',
  navOrder: 130,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/tags',
  name: 'admin-tags',
  component: TagsPage,
  icon: 'fas fa-tags',
  label: '标签管理',
  navDescription: '维护标签结构、排序和可见范围。',
  navSection: 'feature',
  navOrder: 140,
  moduleId: 'tags'
})

registerAdminRoute({
  path: '/admin/mail',
  name: 'admin-mail',
  component: MailPage,
  icon: 'fas fa-envelope',
  label: '邮件设置',
  navDescription: '配置邮件服务和发信能力。',
  navSection: 'feature',
  navOrder: 150,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/advanced',
  name: 'admin-advanced',
  component: AdvancedPage,
  icon: 'fas fa-cog',
  label: '高级设置',
  navDescription: '管理缓存、队列和系统级能力。',
  navSection: 'feature',
  navOrder: 160,
  moduleId: 'core'
})
