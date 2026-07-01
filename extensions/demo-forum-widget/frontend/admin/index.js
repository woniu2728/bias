import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'demo-forum-widget.getting-started',
    path: '/admin/extensions/demo-forum-widget/getting-started',
    label: 'Demo Forum Widget',
    icon: 'fas fa-puzzle-piece',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
