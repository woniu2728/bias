import { Admin } from '@bias/admin'
import TagsPage from './TagsPage.vue'
import { buildTagsPageExtender } from './tagsPageBootstrap.js'

export const extend = [
  new Admin().route({
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
    moduleId: 'tags',
  }).permissionScope({
    key: 'tag-permissions',
    moduleId: 'tags',
    icon: 'fas fa-tags',
    label: '标签权限范围',
    description: '按标签配置查看、发起讨论和回复的访问范围。',
    actionLabel: '管理标签权限',
    to: '/admin/tags',
  }),

  buildTagsPageExtender(),
]

export function resolveSettingsPage() {
  return TagsPage
}
