import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'demo-resource.getting-started',
    path: '/admin/extensions/demo-resource/getting-started',
    label: 'Demo Resource',
    icon: 'fas fa-puzzle-piece',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
