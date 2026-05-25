import DashboardPage from '../../views/DashboardPage.vue'
import ExtensionsPage from '../../views/ExtensionsPage.vue'
import ModulesPage from '../../views/ModulesPage.vue'
import BasicsPage from '../../views/BasicsPage.vue'
import PermissionsPage from '../../views/PermissionsPage.vue'
import UsersPage from '../../views/UsersPage.vue'
import FlagsPage from '../../views/FlagsPage.vue'
import ApprovalQueuePage from '../../views/ApprovalQueuePage.vue'
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
  path: '/admin/extensions',
  name: 'admin-extensions',
  component: ExtensionsPage,
  icon: 'fas fa-plug',
  label: '扩展中心',
  navDescription: '查看扩展清单、状态、依赖与未来设置入口。',
  navSection: 'core',
  navOrder: 20,
  showInDashboardActions: true,
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
  path: '/admin/modules',
  name: 'admin-modules',
  component: ModulesPage,
  icon: 'fas fa-cubes',
  label: '模块中心',
  navDescription: '查看内置模块、扩展能力和注册快照。',
  navSection: 'core',
  navOrder: 25,
  showInDashboardActions: true,
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
  navOrder: 40,
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
  navDescription: '调整主题、Logo 和界面外观。',
  navSection: 'core',
  navOrder: 50,
  showInDashboardActions: true,
  dashboardActionLabel: '自定义外观',
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
  showInDashboardActions: true,
  dashboardActionLabel: '管理用户',
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
  showInDashboardActions: true,
  dashboardActionLabel: '处理审核',
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
  showInDashboardActions: true,
  dashboardActionLabel: '处理举报',
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
  showInDashboardActions: true,
  dashboardActionLabel: '查看审计',
  moduleId: 'core'
})

registerAdminRoute({
  path: '/admin/tags',
  name: 'admin-tags',
  redirect: '/admin/extensions/tags/settings',
  icon: 'fas fa-tags',
  label: '标签管理',
  navDescription: '兼容旧入口，统一跳转到扩展宿主页中的标签设置页。',
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

registerAdminRoute({
  path: '/admin/docs',
  name: 'admin-developer-docs',
  component: DeveloperDocsPage,
  icon: 'fas fa-book',
  label: '开发者文档',
  navDescription: '查看模块开发、资源字段、事件订阅和注册接入指南。',
  navSection: 'feature',
  navOrder: 170,
  moduleId: 'core'
})
