import { computed } from '@bias/core'

export function useDiscussionDetailPermissionState({
  authStore,
  discussion,
  resolveUiText,
}) {
  function uiText(surface, fallback, context = {}) {
    if (typeof resolveUiText !== 'function') {
      return fallback
    }
    return resolveUiText(surface, fallback, context)
  }

  function formatAbsoluteDate(value) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return uiText('discussion-detail-unknown-time', '未知时间')
    return date.toLocaleString('zh-CN')
  }

  const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
  const canEditDiscussion = computed(() => Boolean(
    authStore.isAuthenticated
    && discussion.value?.can_edit
    && !isSuspended.value
  ))
  const canReplyFromMenu = computed(() => Boolean(
    authStore.isAuthenticated
    && discussion.value?.can_reply
    && !discussion.value?.is_locked
    && !isSuspended.value
  ))
  const canModerateDiscussionSettings = computed(() => Boolean(authStore.user?.is_staff))
  const canShowDiscussionMenu = computed(() => canEditDiscussion.value || canModerateDiscussionSettings.value)

  const suspensionNotice = computed(() => {
    if (!isSuspended.value) return ''

    const user = authStore.user || {}
    return uiText(
      'discussion-detail-suspension-notice',
      user.suspended_until
        ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}，暂时无法回复、参与互动或关注讨论。`
        : '账号当前已被封禁，暂时无法回复、参与互动或关注讨论。',
      {
        fallbackMessage: '暂时无法回复、参与互动或关注讨论。',
        suspendedUntilText: user.suspended_until ? formatAbsoluteDate(user.suspended_until) : '',
        user,
      }
    )
  })

  function canEditPost(post) {
    if (isSuspended.value) return false
    return authStore.user?.id === post.user.id || authStore.user?.is_staff
  }

  function canDeletePost(post) {
    if (isSuspended.value) return false
    return authStore.user?.id === post.user.id || authStore.user?.is_staff
  }

  function canReportPost(post) {
    if (!authStore.isAuthenticated) return false
    if (isSuspended.value) return false
    if (!post?.user?.id) return false
    if (post.user.id === authStore.user?.id) return false
    return true
  }

  function canModeratePostVisibility(post) {
    if (!authStore.user?.is_staff) return false
    if (!post) return false
    return post.number > 1
  }

  return {
    canDeletePost,
    canEditDiscussion,
    canEditPost,
    canModerateDiscussionSettings,
    canModeratePostVisibility,
    canReplyFromMenu,
    canReportPost,
    canShowDiscussionMenu,
    formatAbsoluteDate,
    isSuspended,
    suspensionNotice,
  }
}
