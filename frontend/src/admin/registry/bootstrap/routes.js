import DashboardPage from '../../views/DashboardPage.vue'
import BasicsPage from '../../views/BasicsPage.vue'
import PermissionsPage from '../../views/PermissionsPage.vue'
import AuditLogsPage from '../../views/AuditLogsPage.vue'
import AppearancePage from '../../views/AppearancePage.vue'
import MailPage from '../../views/MailPage.vue'
import AdvancedPage from '../../views/AdvancedPage.vue'
import DeveloperDocsPage from '../../views/DeveloperDocsPage.vue'
import ExtensionDetailPage from '../../views/ExtensionDetailPage.vue'
import ExtensionHostPage from '../../views/ExtensionHostPage.vue'
import { registerAdminRoute } from '../routes.js'

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
  path: '/admin/extensions/:extensionId',
  name: 'admin-extension-detail',
  component: ExtensionDetailPage,
  icon: 'fas fa-puzzle-piece',
  label: '扩展详情',
  navDescription: '查看扩展详情、后台入口和运行时状态。',
  navSection: 'core',
  navOrder: 21,
  showInNavigation: false,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/extensions/:extensionId/settings',
  name: 'admin-extension-settings',
  component: ExtensionHostPage,
  icon: 'fas fa-sliders-h',
  label: '扩展设置',
  navDescription: '加载扩展自带的后台设置页面。',
  navSection: 'core',
  navOrder: 22,
  showInNavigation: false,
  moduleId: 'core',
  extensionHostKind: 'settings',
})

registerAdminRoute({
  path: '/admin/extensions/:extensionId/permissions',
  name: 'admin-extension-permissions',
  component: ExtensionHostPage,
  icon: 'fas fa-key',
  label: '扩展权限',
  navDescription: '加载扩展自带的后台权限页面。',
  navSection: 'core',
  navOrder: 23,
  showInNavigation: false,
  moduleId: 'core',
  extensionHostKind: 'permissions',
})

registerAdminRoute({
  path: '/admin/extensions/:extensionId/operations',
  name: 'admin-extension-operations',
  component: ExtensionHostPage,
  icon: 'fas fa-screwdriver-wrench',
  label: '扩展操作',
  navDescription: '加载扩展自带的后台操作页面。',
  navSection: 'core',
  navOrder: 24,
  showInNavigation: false,
  moduleId: 'core',
  extensionHostKind: 'operations',
})

registerAdminRoute({
  path: '/admin/basics',
  name: 'admin-basics',
  component: BasicsPage,
  icon: 'fas fa-pencil-alt',
  label: '基础设置',
  navDescription: '配置论坛的基本信息。',
  navSection: 'core',
  navOrder: 30,
  showInDashboardActions: true,
  dashboardActionLabel: '编辑基础设置',
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
  navOrder: 70,
  showInDashboardActions: true,
  dashboardActionLabel: '管理权限',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/appearance',
  name: 'admin-appearance',
  component: AppearancePage,
  icon: 'fas fa-paint-brush',
  label: '外观设置',
  navDescription: '自定义论坛外观和品牌资源。',
  navSection: 'core',
  navOrder: 40,
  showInDashboardActions: true,
  dashboardActionLabel: '自定义外观',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/audit-logs',
  name: 'admin-audit-logs',
  component: AuditLogsPage,
  icon: 'fas fa-clipboard-list',
  label: '审计日志',
  navDescription: '查看后台操作和敏感变更记录。',
  navSection: 'feature',
  navOrder: 120,
  showInDashboardActions: true,
  dashboardActionLabel: '查看审计',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/mail',
  name: 'admin-mail',
  component: MailPage,
  icon: 'fas fa-envelope',
  label: '邮件设置',
  navDescription: '配置邮件发送方式和发件信息。',
  navSection: 'feature',
  navOrder: 50,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/advanced',
  name: 'admin-advanced',
  component: AdvancedPage,
  icon: 'fas fa-cog',
  label: '高级设置',
  navDescription: '管理高级运行与站点配置。',
  navSection: 'feature',
  navOrder: 60,
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/docs',
  name: 'admin-developer-docs',
  component: DeveloperDocsPage,
  icon: 'fas fa-book',
  label: '开发者文档',
  navDescription: '查看开发者文档与接入说明。',
  navSection: 'feature',
  navOrder: 170,
  showInNavigation: false,
  moduleId: 'core'
})
