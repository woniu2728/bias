import { defineAsyncComponent } from 'vue'
import { buildUserPath } from '@/utils/forum'
import {
  getComposerNotices,
  getComposerSecondaryActions,
  getComposerStatusItems,
  getComposerTools,
  getForumNavItems,
  getForumNavSections,
  getProfilePanels,
  registerDiscussionAction,
  registerComposerNotice,
  registerComposerSecondaryAction,
  registerComposerStatusItem,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerForumNavItem,
  registerForumNavSection,
  registerProfilePanel,
  registerPostAction,
  runComposerSubmitGuards,
} from '@/forum/frontendRegistry'

export {
  getForumNavItems,
  getForumNavSections,
  getComposerNotices,
  getComposerSecondaryActions,
  getComposerStatusItems,
  getComposerTools,
  registerDiscussionAction,
  registerComposerNotice,
  registerComposerSecondaryAction,
  registerComposerStatusItem,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerForumNavItem,
  registerForumNavSection,
  registerProfilePanel,
  registerPostAction,
  runComposerSubmitGuards,
  getProfilePanels,
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

const ProfileDiscussionSection = defineAsyncComponent(() => import('@/components/profile/ProfileDiscussionSection.vue'))
const ProfilePostSection = defineAsyncComponent(() => import('@/components/profile/ProfilePostSection.vue'))
const ProfileSettingsSection = defineAsyncComponent(() => import('@/components/profile/ProfileSettingsSection.vue'))
const ProfileSecuritySection = defineAsyncComponent(() => import('@/components/profile/ProfileSecuritySection.vue'))

registerProfilePanel({
  key: 'discussions',
  label: '讨论',
  icon: 'fas fa-bars',
  order: 10,
  badge: ({ user }) => Number(user?.discussion_count || 0),
  resolve: context => ({
    component: ProfileDiscussionSection,
    componentProps: {
      discussions: context.discussions,
      loading: context.loadingDiscussions,
      isOwnProfile: context.isOwnProfile,
      buildDiscussionPath: context.buildDiscussionPath,
      formatDate: context.formatDate,
    },
  }),
})

registerProfilePanel({
  key: 'posts',
  label: '回复',
  icon: 'far fa-comment',
  order: 20,
  badge: ({ user }) => Number(user?.comment_count || 0),
  resolve: context => ({
    component: ProfilePostSection,
    componentProps: {
      posts: context.posts,
      loading: context.loadingPosts,
      isOwnProfile: context.isOwnProfile,
      buildDiscussionPath: context.buildDiscussionPath,
      formatDate: context.formatDate,
    },
  }),
})

registerProfilePanel({
  key: 'settings',
  label: '设置',
  icon: 'fas fa-user-cog',
  order: 30,
  isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
  resolve: context => ({
    component: ProfileSettingsSection,
    componentProps: {
      user: context.user,
      editForm: context.editForm,
      preferences: context.preferences,
      saving: context.saving,
      settingsSuccess: context.settingsSuccess,
      settingsError: context.settingsError,
      loadingPreferences: context.loadingPreferences,
      savingPreferences: context.savingPreferences,
      preferencesSuccess: context.preferencesSuccess,
      preferencesError: context.preferencesError,
    },
    componentEvents: {
      saveProfile: context.saveProfile,
      savePreferences: context.savePreferences,
    },
  }),
})

registerProfilePanel({
  key: 'security',
  label: '安全',
  icon: 'fas fa-shield-alt',
  order: 40,
  isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
  resolve: context => ({
    component: ProfileSecuritySection,
    componentProps: {
      user: context.user,
      passwordForm: context.passwordForm,
      verificationSending: context.verificationSending,
      verificationSuccess: context.verificationSuccess,
      verificationError: context.verificationError,
      changingPassword: context.changingPassword,
      passwordSuccess: context.passwordSuccess,
      passwordError: context.passwordError,
    },
    componentEvents: {
      resendVerification: context.resendVerificationEmail,
      changePassword: context.changePassword,
    },
  }),
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

registerComposerSecondaryAction({
  key: 'clear-discussion-draft',
  order: 10,
  isVisible: ({ type, isEditing, hasDraftContent }) => type === 'discussion' && !isEditing && Boolean(hasDraftContent),
  resolve: ({ draftSavedAt }) => ({
    label: '清除草稿',
    action: 'clear-draft',
    confirm: draftSavedAt ? {
      title: '清除讨论草稿',
      message: '确定要清除当前讨论草稿吗？',
      confirmText: '清除草稿',
      cancelText: '取消',
      tone: 'danger',
    } : null,
  }),
})

registerComposerSecondaryAction({
  key: 'clear-post-draft',
  order: 10,
  isVisible: ({ type, isEditing, hasDraftContent }) => type === 'post' && !isEditing && Boolean(hasDraftContent),
  resolve: ({ draftSavedAt }) => ({
    label: '清除草稿',
    action: 'clear-draft',
    confirm: draftSavedAt ? {
      title: '清除回复草稿',
      message: '确定要清除当前回复草稿吗？',
      confirmText: '清除草稿',
      cancelText: '取消',
      tone: 'danger',
    } : null,
  }),
})

registerComposerSecondaryAction({
  key: 'cancel-post-edit',
  order: 20,
  isVisible: ({ type, isEditing }) => type === 'post' && Boolean(isEditing),
  resolve: () => ({
    label: '取消编辑',
    action: 'cancel-edit',
    confirm: {
      title: '取消编辑',
      message: '确定放弃当前回复编辑内容吗？未保存修改将丢失。',
      confirmText: '放弃修改',
      cancelText: '继续编辑',
      tone: 'warning',
    },
  }),
})

registerComposerSecondaryAction({
  key: 'save-discussion-draft',
  order: 5,
  isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
    return type === 'discussion' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
  },
  resolve: () => ({
    label: '保存草稿',
    onClick: async ({ composerStore }) => {
      window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
        detail: {
          composerType: 'discussion',
          requestId: composerStore?.current?.requestId || 0,
        },
      }))
    },
  }),
})

registerComposerSecondaryAction({
  key: 'save-post-draft',
  order: 5,
  isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
    return type === 'post' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
  },
  resolve: () => ({
    label: '保存草稿',
    onClick: async ({ composerStore }) => {
      window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
        detail: {
          composerType: 'post',
          requestId: composerStore?.current?.requestId || 0,
        },
      }))
    },
  }),
})

registerComposerStatusItem({
  key: 'discussion-selected-tag',
  order: 10,
  isVisible: ({ type, selectedTagLabel, minimized }) => type === 'discussion' && Boolean(selectedTagLabel) && !minimized,
  resolve: ({ selectedTagLabel }) => ({
    label: '标签',
    value: selectedTagLabel,
  }),
})

registerComposerStatusItem({
  key: 'discussion-editing',
  order: 20,
  isVisible: ({ type, isEditing, minimized }) => type === 'discussion' && Boolean(isEditing) && !minimized,
  resolve: () => ({
    label: '状态',
    value: '编辑讨论',
  }),
})

registerComposerStatusItem({
  key: 'discussion-draft-saved-at',
  order: 30,
  isVisible: ({ type, draftSavedAt, minimized }) => type === 'discussion' && Boolean(draftSavedAt) && !minimized,
  resolve: ({ draftSavedAt, formatDraftTime }) => ({
    label: '草稿',
    value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
  }),
})

registerComposerStatusItem({
  key: 'post-editing',
  order: 10,
  isVisible: ({ type, isEditing, minimized }) => type === 'post' && Boolean(isEditing) && !minimized,
  resolve: ({ postNumber }) => ({
    label: '状态',
    value: postNumber ? `编辑 #${postNumber}` : '编辑回复',
  }),
})

registerComposerStatusItem({
  key: 'post-target',
  order: 20,
  isVisible: ({ type, discussionTitle, minimized }) => type === 'post' && Boolean(discussionTitle) && !minimized,
  resolve: ({ discussionTitle, username }) => ({
    label: '讨论',
    value: username ? `${discussionTitle} · @${username}` : discussionTitle,
  }),
})

registerComposerStatusItem({
  key: 'post-draft-saved-at',
  order: 30,
  isVisible: ({ type, draftSavedAt, isEditing, minimized }) => {
    return type === 'post' && !isEditing && Boolean(draftSavedAt) && !minimized
  },
  resolve: ({ draftSavedAt, formatDraftTime }) => ({
    label: '草稿',
    value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
  }),
})
