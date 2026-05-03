const discussionMenuItemFactories = []
const postMenuItemFactories = []

export function registerDiscussionMenuItem(factory) {
  discussionMenuItemFactories.push(factory)
}

export function registerPostMenuItem(factory) {
  postMenuItemFactories.push(factory)
}

export function getDiscussionMenuItems(context) {
  return discussionMenuItemFactories
    .map(factory => factory(context))
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

export function getPostMenuItems(context) {
  return postMenuItemFactories
    .map(factory => factory(context))
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

registerDiscussionMenuItem(({ canReplyFromMenu, hasActiveComposer }) => {
  if (!canReplyFromMenu) return null
  return {
    key: 'reply',
    label: hasActiveComposer ? '继续回复' : '回复讨论',
    order: 10
  }
})

registerDiscussionMenuItem(({ canReplyFromMenu }) => {
  if (canReplyFromMenu) return null
  return {
    key: 'login',
    label: '登录后回复',
    order: 10
  }
})

registerDiscussionMenuItem(({ authStore, isSuspended, togglingSubscription, discussion }) => {
  if (!authStore?.isAuthenticated || isSuspended) return null
  return {
    key: 'toggle-subscription',
    label: togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注讨论'),
    order: 20
  }
})

registerDiscussionMenuItem(({ canEditDiscussion }) => {
  if (!canEditDiscussion) return null
  return {
    key: 'edit',
    label: '编辑讨论',
    order: 30
  }
})

registerDiscussionMenuItem(({ canModerateDiscussionSettings, discussion }) => {
  if (!canModerateDiscussionSettings) return null
  return {
    key: 'toggle-pin',
    label: discussion.is_sticky ? '取消置顶' : '置顶讨论',
    order: 40
  }
})

registerDiscussionMenuItem(({ canModerateDiscussionSettings, discussion }) => {
  if (!canModerateDiscussionSettings) return null
  return {
    key: 'toggle-lock',
    label: discussion.is_locked ? '解除锁定' : '锁定讨论',
    order: 50
  }
})

registerDiscussionMenuItem(({ canModerateDiscussionSettings, discussion }) => {
  if (!canModerateDiscussionSettings) return null
  return {
    key: 'toggle-hide',
    label: discussion.is_hidden ? '恢复显示' : '隐藏讨论',
    order: 60
  }
})

registerDiscussionMenuItem(({ canModerateDiscussionSettings }) => {
  if (!canModerateDiscussionSettings) return null
  return {
    key: 'delete',
    label: '删除讨论',
    tone: 'danger',
    order: 70
  }
})

registerPostMenuItem(({ post, canEditPost }) => {
  if (!canEditPost(post)) return null
  return {
    key: 'edit-post',
    label: '编辑',
    order: 10
  }
})

registerPostMenuItem(({ post, canDeletePost }) => {
  if (!canDeletePost(post)) return null
  return {
    key: 'delete-post',
    label: '删除',
    tone: 'danger',
    order: 20
  }
})

registerPostMenuItem(({ post, canReportPost }) => {
  if (!canReportPost(post)) return null
  return {
    key: 'open-report-modal',
    label: '举报',
    order: 30
  }
})
