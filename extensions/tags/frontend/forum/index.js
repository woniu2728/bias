import { registerForumNavItem } from '@/forum/registry'

export async function bootForumExtension() {
  registerForumNavItem({
    key: 'tags',
    moduleId: 'tags',
    to: '/tags',
    icon: 'fas fa-tags',
    label: '全部标签',
    description: '按标签浏览论坛主题。',
    section: 'primary',
    order: 30,
    surfaces: ['primary-nav', 'discussion-sidebar', 'mobile-drawer']
  })
}
