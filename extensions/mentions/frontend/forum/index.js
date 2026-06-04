import {
  registerComposerMentionProvider,
  registerComposerTool,
  registerNotificationRenderer,
  registerStateBlock,
  registerUiCopy,
} from '@/forum/registry'

export async function bootForumExtension({ api } = {}) {
  registerComposerTool({
    key: 'mention',
    moduleId: 'mentions',
    order: 130,
    title: '@ 提及',
    icon: 'fas fa-at',
    before: '@',
    after: '',
  })

  registerStateBlock({
    key: 'mentions-composer-loading',
    moduleId: 'mentions',
    order: 100,
    surfaces: ['composer-mention-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: '搜索中...',
    }),
  })

  registerStateBlock({
    key: 'mentions-composer-empty',
    moduleId: 'mentions',
    order: 110,
    surfaces: ['composer-mention-empty'],
    isVisible: ({ loading, itemCount }) => !loading && Number(itemCount || 0) === 0,
    resolve: () => ({
      text: '没有匹配的用户',
    }),
  })

  registerUiCopy({
    key: 'mentions-composer-picker-label',
    moduleId: 'mentions',
    order: 1080,
    surfaces: ['composer-mention-picker-label'],
    resolve: () => ({
      text: '提及用户',
    }),
  })

  registerComposerMentionProvider({
    key: 'mentions-users',
    moduleId: 'mentions',
    order: 10,
    async search({ mentionQuery = '', limit = 5 }) {
      if (typeof api?.get !== 'function') {
        return []
      }
      const users = await api.get('/users', {
        params: {
          q: mentionQuery,
          limit,
        },
      })
      return Array.isArray(users) ? users.slice(0, limit) : []
    },
  })

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
