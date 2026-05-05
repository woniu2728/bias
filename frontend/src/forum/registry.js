import { buildUserPath } from '@/utils/forum'
import {
  getComposerNotices,
  getComposerTools,
  getForumNavItems,
  getForumNavSections,
  registerDiscussionAction,
  registerComposerNotice,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerForumNavItem,
  registerForumNavSection,
  registerPostAction,
  runComposerSubmitGuards,
} from '@/forum/frontendRegistry'

export {
  getForumNavItems,
  getForumNavSections,
  getComposerNotices,
  getComposerTools,
  registerDiscussionAction,
  registerComposerNotice,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerForumNavItem,
  registerForumNavSection,
  registerPostAction,
  runComposerSubmitGuards,
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
  order: 10,
  surfaces: ['primary-nav', 'discussion-sidebar', 'mobile-drawer']
})

registerForumNavItem({
  key: 'following',
  to: '/following',
  icon: 'fas fa-bell',
  label: '关注中',
  description: '查看你关注讨论的更新。',
  section: 'primary',
  order: 20,
  surfaces: ['discussion-sidebar', 'mobile-drawer'],
  isVisible: ({ authStore }) => Boolean(authStore?.user)
})

registerForumNavItem({
  key: 'tags',
  to: '/tags',
  icon: 'fas fa-tags',
  label: '全部标签',
  description: '按标签浏览论坛主题。',
  section: 'primary',
  order: 30,
  surfaces: ['primary-nav', 'mobile-drawer']
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
  surfaces: ['discussion-sidebar', 'mobile-drawer'],
  isVisible: ({ authStore }) => Boolean(authStore?.user)
})

function formatComposerSuspensionNotice(user = {}, fallbackMessage) {
  if (!user?.is_suspended) return ''

  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}，${fallbackMessage}`
    : `账号当前已被封禁，${fallbackMessage}`
}

function formatComposerDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

registerComposerNotice({
  key: 'suspension',
  order: 10,
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
  resolve: ({ authStore, type }) => ({
    label: '账号',
    tone: 'warning',
    message: formatComposerSuspensionNotice(
      authStore.user,
      type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
    ),
  }),
})

registerComposerNotice({
  key: 'approval-feedback',
  order: 20,
  isVisible: ({ isEditing, composerStore }) => {
    return Boolean(
      isEditing
      && composerStore?.current?.approvalStatus === 'rejected'
      && composerStore?.current?.approvalNote
    )
  },
  resolve: ({ type, composerStore }) => ({
    label: type === 'discussion' ? '讨论审核反馈' : '回复审核反馈',
    tone: 'warning',
    message: composerStore.current.approvalNote,
  }),
})

registerComposerNotice({
  key: 'discussion-tag-permission',
  order: 30,
  isVisible: ({ type, availablePrimaryTagCount }) => {
    return type === 'discussion' && Number(availablePrimaryTagCount || 0) <= 0
  },
  resolve: () => ({
    label: '标签',
    tone: 'warning',
    message: '当前没有可发帖的标签，请联系管理员开放标签权限。',
  }),
})

registerComposerNotice({
  key: 'discussion-tag-selection',
  order: 40,
  isVisible: ({ type, availablePrimaryTagCount, primaryTagId }) => {
    return type === 'discussion' && Number(availablePrimaryTagCount || 0) > 0 && !primaryTagId
  },
  resolve: () => ({
    label: '标签',
    tone: 'info',
    message: '先选择主标签，再发布讨论。',
  }),
})

registerComposerTool({
  key: 'discussion-template',
  order: 15,
  isVisible: ({ type }) => type === 'discussion',
  resolve: () => ({
    title: '插入讨论模板',
    icon: 'fas fa-clipboard-list',
    async run({ content, insertText, selectionStart, selectionEnd }) {
      const template = [
        '## 背景',
        '',
        '简要说明当前问题或主题背景。',
        '',
        '## 现象',
        '',
        '描述你观察到的结果、错误或争议点。',
        '',
        '## 期望',
        '',
        '说明希望获得的帮助、答案或改进方向。'
      ].join('\n')

      const prefix = content.trim() ? '\n\n' : ''
      const replacement = `${prefix}${template}`
      const cursor = selectionStart + replacement.length
      await insertText(replacement, {
        start: selectionStart,
        end: selectionEnd,
        cursor,
      })
    },
  }),
})

registerComposerSubmitGuard({
  key: 'suspension',
  order: 10,
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
  check: ({ authStore, type }) => ({
    tone: 'error',
    message: formatComposerSuspensionNotice(
      authStore.user,
      type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
    ),
  }),
})

registerComposerSubmitGuard({
  key: 'discussion-start-permission',
  order: 20,
  isVisible: ({ type, mode }) => type === 'discussion' && mode === 'create',
  check: ({ authStore }) => {
    if (authStore?.canStartDiscussion) return null
    return {
      tone: 'error',
      message: '当前账号没有发起讨论的权限。',
    }
  },
})

registerComposerSubmitGuard({
  key: 'discussion-primary-tag',
  order: 30,
  isVisible: ({ type }) => type === 'discussion',
  check: ({ availablePrimaryTagCount, primaryTagId }) => {
    if (Number(availablePrimaryTagCount || 0) <= 0) {
      return {
        tone: 'error',
        message: '当前没有可用主标签，暂时无法发布讨论。',
      }
    }

    if (primaryTagId) return null
    return {
      tone: 'error',
      message: '请选择主标签后再发布讨论。',
    }
  },
})
