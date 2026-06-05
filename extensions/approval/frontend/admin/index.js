import { ExtensionGeneratedPermissionsPage, registerAdminDashboardStat, registerAdminRoute } from '@/admin/registry'
import ApprovalQueuePage from './ApprovalQueuePage.vue'
import './approvalQueuePageBootstrap.js'

export function bootAdminExtension() {
  registerAdminDashboardStat({
    key: 'pending-approvals',
    order: 40,
    icon: 'fas fa-user-check',
    iconClass: 'StatsWidget-icon--info',
    moduleId: 'approval',
    resolve: ({ stats, copy }) => ({
      label: copy?.pendingApprovalsStatLabel || '待审核内容',
      value: stats?.pendingApprovals || 0,
    }),
  })

  registerAdminRoute({
    path: '/admin/approval',
    name: 'admin-approval',
    component: ApprovalQueuePage,
    icon: 'fas fa-user-check',
    label: '审核队列',
    navDescription: '审核待放行的讨论和回复内容。',
    navSection: 'feature',
    navOrder: 110,
    showInNavigation: true,
    showInDashboardActions: true,
    dashboardActionLabel: '处理审核',
    moduleId: 'approval',
  })
}

export function resolveOperationsPage() {
  return ApprovalQueuePage
}

export function resolvePermissionsPage() {
  return ExtensionGeneratedPermissionsPage
}
