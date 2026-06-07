import { extendAdmin } from '@bias/admin'
import { ExtensionGeneratedPermissionsPage } from '@bias/admin/components'
import FlagsPage from './FlagsPage.vue'
import { buildFlagsPageExtender } from './flagsPageBootstrap.js'

export const extend = [
  extendAdmin(admin => admin.route({
    path: '/admin/flags',
    name: 'admin-flags',
    component: FlagsPage,
    icon: 'fas fa-flag',
    label: '举报管理',
    navDescription: '处理用户提交的举报与内容风险。',
    navSection: 'feature',
    navOrder: 100,
    showInNavigation: true,
    showInDashboardActions: true,
    dashboardActionLabel: '处理举报',
    moduleId: 'flags',
  }).dashboardStat({
    key: 'open-flags',
    order: 50,
    icon: 'fas fa-flag',
    iconClass: 'StatsWidget-icon--warning',
    moduleId: 'flags',
    resolve: ({ stats, copy }) => ({
      label: copy?.openFlagsStatLabel || '待处理举报',
      value: stats?.openFlags || 0,
    }),
  })),

  buildFlagsPageExtender(),
]

export function resolveOperationsPage() {
  return FlagsPage
}

export function resolvePermissionsPage() {
  return ExtensionGeneratedPermissionsPage
}
