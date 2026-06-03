import { registerAdminRoute } from '@/admin/registry'
import TagsPage from './TagsPage.vue'
import './tagsPageBootstrap.js'

export function bootAdminExtension() {
  registerAdminRoute({
    path: '/admin/tags',
    name: 'admin-tags',
    component: TagsPage,
    icon: 'fas fa-tags',
    label: '标签管理',
    navDescription: '管理论坛标签层级、排序与发帖限制。',
    navSection: 'feature',
    navOrder: 90,
    showInNavigation: true,
    showInDashboardActions: true,
    dashboardActionLabel: '管理标签',
    moduleId: 'tags'
  })
}

export function resolveSettingsPage() {
  return TagsPage
}
