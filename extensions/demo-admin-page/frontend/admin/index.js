import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'demo-admin-page.getting-started',
    path: '/admin/extensions/demo-admin-page/getting-started',
    label: 'Demo Admin Page',
    icon: 'fas fa-table-columns',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
