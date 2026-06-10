import { extendAdmin } from '@bias/admin'

export const extend = [
  extendAdmin(admin => admin.dashboardStat({
    key: 'posts',
    order: 30,
    icon: 'fas fa-comment',
    moduleId: 'posts',
    resolve: ({ stats, copy }) => ({
      label: copy?.postsStatLabel || '帖子总数',
      value: stats?.totalPosts || 0,
    }),
  })),
]

export function resolveDetailPage() {
  return null
}
