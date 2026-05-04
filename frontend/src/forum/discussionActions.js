import {
  getDiscussionActions,
  getPostActions,
  registerDiscussionAction,
  registerPostAction,
} from '@/forum/frontendRegistry'

export function registerDiscussionMenuItem(factory) {
  return registerDiscussionAction({
    key: `legacy-discussion-action-${Date.now()}-${Math.random()}`,
    isVisible: context => Boolean(factory(context)),
    resolve: factory,
  })
}

export function registerPostMenuItem(factory) {
  return registerPostAction({
    key: `legacy-post-action-${Date.now()}-${Math.random()}`,
    isVisible: context => Boolean(factory(context)),
    resolve: factory,
  })
}

export function getDiscussionMenuItems(context) {
  return getDiscussionActions(context)
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

export function getPostMenuItems(context) {
  return getPostActions(context)
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

registerDiscussionAction({
  key: 'reply',
  order: 10,
  isVisible: ({ canReplyFromMenu }) => Boolean(canReplyFromMenu),
  resolve: ({ hasActiveComposer }) => ({
    key: 'reply',
    label: hasActiveComposer ? '继续回复' : '回复讨论',
    icon: 'fas fa-reply',
    description: hasActiveComposer ? '继续当前未发布的回复草稿。' : '在当前讨论中开始撰写回复。',
    order: 10
  })
})

registerDiscussionAction({
  key: 'login',
  order: 10,
  isVisible: ({ canReplyFromMenu }) => !canReplyFromMenu,
  resolve: () => ({
    key: 'login',
    label: '登录后回复',
    icon: 'fas fa-sign-in-alt',
    description: '登录后才可以参与当前讨论。',
    order: 10
  })
})

registerDiscussionAction({
  key: 'toggle-subscription',
  order: 20,
  isVisible: ({ authStore, isSuspended }) => Boolean(authStore?.isAuthenticated) && !isSuspended,
  resolve: ({ togglingSubscription, discussion }) => ({
    key: 'toggle-subscription',
    label: togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注讨论'),
    icon: discussion.is_subscribed ? 'fas fa-bell-slash' : 'far fa-star',
    description: discussion.is_subscribed ? '停止接收这条讨论后续回复通知。' : '接收这条讨论后续回复通知。',
    disabled: togglingSubscription,
    disabledReason: togglingSubscription ? '正在提交关注状态，请稍候。' : '',
    order: 20
  })
})

registerDiscussionAction({
  key: 'edit',
  order: 30,
  isVisible: ({ canEditDiscussion }) => Boolean(canEditDiscussion),
  resolve: () => ({
    key: 'edit',
    label: '编辑讨论',
    icon: 'fas fa-pen',
    description: '修改标题、正文和标签。',
    order: 30
  })
})

registerDiscussionAction({
  key: 'toggle-pin',
  order: 40,
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-pin',
    label: discussion.is_sticky ? '取消置顶' : '置顶讨论',
    icon: 'fas fa-thumbtack',
    description: discussion.is_sticky ? '把讨论恢复为普通排序。' : '把讨论固定到列表更靠前的位置。',
    confirm: discussion.is_sticky ? null : {
      title: '置顶讨论',
      message: '确定将这条讨论置顶吗？',
      confirmText: '置顶讨论',
      cancelText: '取消',
      tone: 'primary',
    },
    order: 40
  })
})

registerDiscussionAction({
  key: 'toggle-lock',
  order: 50,
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-lock',
    label: discussion.is_locked ? '解除锁定' : '锁定讨论',
    icon: discussion.is_locked ? 'fas fa-lock-open' : 'fas fa-lock',
    description: discussion.is_locked ? '恢复普通用户回复能力。' : '阻止普通用户继续回复。',
    confirm: discussion.is_locked ? null : {
      title: '锁定讨论',
      message: '确定锁定当前讨论并阻止普通用户继续回复吗？',
      confirmText: '锁定讨论',
      cancelText: '取消',
      tone: 'warning',
    },
    order: 50
  })
})

registerDiscussionAction({
  key: 'toggle-hide',
  order: 60,
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-hide',
    label: discussion.is_hidden ? '恢复显示' : '隐藏讨论',
    icon: discussion.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
    description: discussion.is_hidden ? '重新让讨论出现在前台列表。' : '临时从前台列表隐藏当前讨论。',
    confirm: {
      title: discussion.is_hidden ? '恢复显示' : '隐藏讨论',
      message: discussion.is_hidden ? '确定恢复显示当前讨论吗？' : '确定从前台列表隐藏当前讨论吗？',
      confirmText: discussion.is_hidden ? '恢复显示' : '隐藏讨论',
      cancelText: '取消',
      tone: discussion.is_hidden ? 'primary' : 'warning',
    },
    order: 60
  })
})

registerDiscussionAction({
  key: 'delete',
  order: 70,
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: () => ({
    key: 'delete',
    label: '删除讨论',
    icon: 'fas fa-trash',
    description: '永久删除当前讨论及其回复。',
    tone: 'danger',
    confirm: {
      title: '删除讨论',
      message: '确定要删除这个讨论吗？此操作不可恢复。',
      confirmText: '删除',
      cancelText: '取消',
      tone: 'danger',
    },
    order: 70
  })
})

registerPostAction({
  key: 'edit-post',
  order: 10,
  isVisible: ({ post, canEditPost }) => Boolean(canEditPost(post)),
  resolve: () => ({
    key: 'edit-post',
    label: '编辑',
    icon: 'fas fa-pen',
    description: '修改这条回复内容。',
    order: 10
  })
})

registerPostAction({
  key: 'delete-post',
  order: 20,
  isVisible: ({ post, canDeletePost }) => Boolean(canDeletePost(post)),
  resolve: () => ({
    key: 'delete-post',
    label: '删除',
    icon: 'fas fa-trash',
    description: '永久删除这条回复。',
    tone: 'danger',
    confirm: {
      title: '删除回复',
      message: '确定要删除这条回复吗？此操作不可恢复。',
      confirmText: '删除',
      cancelText: '取消',
      tone: 'danger',
    },
    order: 20
  })
})

registerPostAction({
  key: 'toggle-hide-post',
  order: 25,
  isVisible: ({ post, canModeratePostVisibility }) => Boolean(canModeratePostVisibility?.(post)),
  resolve: ({ post }) => ({
    key: 'toggle-hide-post',
    label: post.is_hidden ? '恢复显示' : '隐藏回复',
    icon: post.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
    description: post.is_hidden ? '重新让这条回复在前台可见。' : '临时从前台隐藏这条回复。',
    confirm: {
      title: post.is_hidden ? '恢复显示' : '隐藏回复',
      message: post.is_hidden ? `确定恢复显示 #${post.number} 吗？` : `确定隐藏 #${post.number} 吗？`,
      confirmText: post.is_hidden ? '恢复显示' : '隐藏回复',
      cancelText: '取消',
      tone: post.is_hidden ? 'primary' : 'warning',
    },
    order: 25
  })
})

registerPostAction({
  key: 'open-report-modal',
  order: 30,
  isVisible: ({ post, canReportPost }) => Boolean(canReportPost(post)),
  resolve: () => ({
    key: 'open-report-modal',
    label: '举报',
    icon: 'fas fa-flag',
    description: '向版主提交这条回复的问题反馈。',
    order: 30
  })
})
