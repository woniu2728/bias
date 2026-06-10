import { extendAdmin } from '@bias/admin'
import { ExtensionGeneratedPermissionsPage } from '@bias/admin/components'

export const extend = [
  extendAdmin(admin => admin.dashboardStat({
    key: 'discussions',
    order: 20,
    icon: 'fas fa-comments',
    moduleId: 'discussions',
    resolve: ({ stats, copy }) => ({
      label: copy?.discussionsStatLabel || '讨论总数',
      value: stats?.totalDiscussions || 0,
    }),
  })),
]

export function resolvePermissionsPage() {
  return ExtensionGeneratedPermissionsPage
}
