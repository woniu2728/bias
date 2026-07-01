import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'demo-settings.getting-started',
    path: '/admin/extensions/demo-settings/getting-started',
    label: 'Demo Settings',
    icon: 'fas fa-puzzle-piece',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
