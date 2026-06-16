import { api } from '@bias/core'
import { extendForum } from '@bias/forum'
import ComposerMentionAutocomplete from './ComposerMentionAutocomplete.vue'
import {
  buildMentionReplacement,
  buildMentionTrigger,
  detectMentionQuery,
} from './mentionRuntime.js'

export const extend = [
  extendForum(registerMentionsForum),
]

function registerMentionsForum(forum) {
  forum.composerTool({
    key: 'mention',
    moduleId: 'mentions',
    order: 130,
    title: '@ 提及',
    icon: 'fas fa-at',
    run: async ({ content, insertText, selectionStart, selectionEnd }) => {
      const replacement = buildMentionTrigger(content, selectionStart)
      await insertText(replacement, {
        start: selectionStart,
        end: selectionEnd,
        cursor: selectionStart + replacement.length,
      })
    },
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

  forum.composerAutocompleteProvider({
    key: 'mentions-users-autocomplete',
    moduleId: 'mentions',
    order: 10,
    renderer: 'mention',
    component: ComposerMentionAutocomplete,
    showWhenEmpty: true,
    height: 280,
    limit: 5,
    debounce: 150,
    detect({ content = '', cursorPosition }) {
      return detectMentionQuery(content, cursorPosition)
    },
    async search({ query = '', limit = 5 }) {
      if (typeof api?.get !== 'function') {
        return []
      }
      const users = await api.get('/users', {
        params: {
          q: query,
          limit,
        },
      })
      return Array.isArray(users) ? users.slice(0, limit) : []
    },
    replacement({ item }) {
      return buildMentionReplacement(item?.username)
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
