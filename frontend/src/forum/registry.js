import { buildUserPath } from '@/utils/forum'
import {
  getForumNavItems,
  getForumNavSections,
  registerDiscussionAction,
  registerForumNavItem,
  registerForumNavSection,
  registerPostAction,
} from '@/forum/frontendRegistry'

export {
  getForumNavItems,
  getForumNavSections,
  registerDiscussionAction,
  registerForumNavItem,
  registerForumNavSection,
  registerPostAction,
}

registerForumNavSection({
  key: 'primary',
  title: '',
  order: 10,
})

registerForumNavSection({
  key: 'personal',
  title: '个人',
  order: 20,
})

registerForumNavItem({
  key: 'home',
  to: '/',
  icon: 'far fa-comments',
  label: '全部讨论',
  description: '查看全站最新讨论流。',
  section: 'primary',
  order: 10
})

registerForumNavItem({
  key: 'following',
  to: '/following',
  icon: 'fas fa-bell',
  label: '关注中',
  description: '查看你关注讨论的更新。',
  section: 'primary',
  order: 20,
  isVisible: ({ authStore }) => Boolean(authStore?.user)
})

registerForumNavItem({
  key: 'tags',
  to: '/tags',
  icon: 'fas fa-tags',
  label: '全部标签',
  description: '按标签浏览论坛主题。',
  section: 'primary',
  order: 30
})

registerForumNavItem({
  key: 'notifications',
  to: '/notifications',
  icon: 'fas fa-inbox',
  label: '通知',
  description: '查看回复、提及和审核通知。',
  section: 'personal',
  order: 40,
  badge: ({ notificationStore }) => {
    const count = Number(notificationStore?.unreadCount || 0)
    return count > 0 ? count : ''
  },
  isVisible: ({ showNotifications }) => Boolean(showNotifications)
})

registerForumNavItem({
  key: 'profile',
  to: ({ authStore }) => buildUserPath(authStore.user),
  icon: 'fas fa-user',
  label: '我的主页',
  description: '查看你的资料、讨论和回复。',
  section: 'personal',
  order: 50,
  isVisible: ({ authStore }) => Boolean(authStore?.user)
})
