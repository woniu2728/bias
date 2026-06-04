import { registerNotificationRenderer } from '@/forum/registry'

export async function bootForumExtension() {
  registerNotificationRenderer({
    type: 'userMentioned',
    key: 'userMentioned',
    moduleId: 'mentions',
    label: '@提及通知',
    icon: 'fas fa-at',
    navigationScope: 'post',
    groupLabel: '互动反馈',
    order: 30,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      return `${fromUser} 在回复中提到了你`
    },
  })
}
