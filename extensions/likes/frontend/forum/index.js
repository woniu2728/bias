import { registerNotificationRenderer } from '@/forum/registry'

export async function bootForumExtension() {
  registerNotificationRenderer({
    type: 'postLiked',
    key: 'postLiked',
    moduleId: 'likes',
    label: '回复被点赞',
    icon: 'fas fa-thumbs-up',
    navigationScope: 'post',
    groupLabel: '互动反馈',
    order: 20,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      return `${fromUser} 点赞了你的回复`
    },
  })
}
