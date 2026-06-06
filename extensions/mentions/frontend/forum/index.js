import { Forum } from '@bias/forum'
import {
  forumApi,
} from '@/forum/registry'

export const extend = [
  buildMentionsForumExtender(),
]

function buildMentionsForumExtender() {
  const forum = new Forum()
  registerMentionsForum(forum)
  return forum
}

function registerMentionsForum(forum) {
  forum.composerTool({
    key: 'mention',
    moduleId: 'mentions',
    order: 130,
    title: '@ 提及',
    icon: 'fas fa-at',
    before: '@',
    after: '',
  })

  forum.stateBlock({
    key: 'mentions-composer-loading',
    moduleId: 'mentions',
    order: 100,
    surfaces: ['composer-mention-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: '搜索中...',
    }),
  })

  forum.stateBlock({
    key: 'mentions-composer-empty',
    moduleId: 'mentions',
    order: 110,
    surfaces: ['composer-mention-empty'],
    isVisible: ({ loading, itemCount }) => !loading && Number(itemCount || 0) === 0,
    resolve: () => ({
      text: '没有匹配的用户',
    }),
  })

  forum.uiCopy({
    key: 'mentions-composer-picker-label',
    moduleId: 'mentions',
    order: 1080,
    surfaces: ['composer-mention-picker-label'],
    resolve: () => ({
      text: '提及用户',
    }),
  })

  forum.composerMentionProvider({
    key: 'mentions-users',
    moduleId: 'mentions',
    order: 10,
    async search({ mentionQuery = '', limit = 5 }) {
      if (typeof forumApi?.get !== 'function') {
        return []
      }
      const users = await forumApi.get('/users', {
        params: {
          q: mentionQuery,
          limit,
        },
      })
      return Array.isArray(users) ? users.slice(0, limit) : []
    },
  })

  forum.notificationRenderer({
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
