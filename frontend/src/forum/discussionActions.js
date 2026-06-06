import {
  getDiscussionActions,
  getPostActions,
  getUiCopy,
  registerDiscussionAction,
  registerPostAction,
} from '@/forum/registry'

export function registerDiscussionMenuItem(factory) {
  return registerDiscussionAction({
    key: `external-discussion-action-${Date.now()}-${Math.random()}`,
    isVisible: context => Boolean(factory(context)),
    resolve: factory,
  })
}

export function registerPostMenuItem(factory) {
  return registerPostAction({
    key: `external-post-action-${Date.now()}-${Math.random()}`,
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
  moduleId: 'posts',
  order: 10,
  surfaces: ['discussion-sidebar', 'discussion-menu'],
  isVisible: ({ canReplyFromMenu }) => Boolean(canReplyFromMenu),
  resolve: ({ hasActiveComposer }) => ({
    key: 'reply',
    label: getUiCopy({
      surface: 'discussion-action-reply-label',
      hasActiveComposer,
    })?.text || (hasActiveComposer ? '继续回复' : '回复讨论'),
    icon: 'fas fa-reply',
    description: getUiCopy({
      surface: 'discussion-action-reply-description',
      hasActiveComposer,
    })?.text || (hasActiveComposer ? '继续当前未发布的回复草稿。' : '在当前讨论中开始撰写回复。'),
    order: 10
  })
})

registerDiscussionAction({
  key: 'login',
  moduleId: 'posts',
  order: 10,
  surfaces: ['discussion-sidebar', 'discussion-menu'],
  isVisible: ({ canReplyFromMenu }) => !canReplyFromMenu,
  resolve: () => ({
    key: 'login',
    label: getUiCopy({
      surface: 'discussion-action-login-label',
    })?.text || '登录后回复',
    icon: 'fas fa-sign-in-alt',
    description: getUiCopy({
      surface: 'discussion-action-login-description',
    })?.text || '登录后才可以参与当前讨论。',
    order: 10
  })
})

registerDiscussionAction({
  key: 'edit',
  moduleId: 'discussions',
  order: 30,
  surfaces: ['discussion-menu'],
  isVisible: ({ canEditDiscussion }) => Boolean(canEditDiscussion),
  resolve: () => ({
    key: 'edit',
    label: getUiCopy({
      surface: 'discussion-action-edit-label',
    })?.text || '编辑讨论',
    icon: 'fas fa-pen',
    description: getUiCopy({
      surface: 'discussion-action-edit-description',
    })?.text || '修改标题和正文。',
    order: 30
  })
})

registerDiscussionAction({
  key: 'toggle-pin',
  moduleId: 'discussions',
  order: 40,
  surfaces: ['discussion-menu'],
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-pin',
    label: getUiCopy({
      surface: 'discussion-action-toggle-pin-label',
      isSticky: discussion.is_sticky,
    })?.text || (discussion.is_sticky ? '取消置顶' : '置顶讨论'),
    icon: 'fas fa-thumbtack',
    description: getUiCopy({
      surface: 'discussion-action-toggle-pin-description',
      isSticky: discussion.is_sticky,
    })?.text || (discussion.is_sticky ? '把讨论恢复为普通排序。' : '把讨论固定到列表更靠前的位置。'),
    confirm: discussion.is_sticky ? null : {
      title: getUiCopy({
        surface: 'discussion-action-toggle-pin-confirm-title',
      })?.text || '置顶讨论',
      message: getUiCopy({
        surface: 'discussion-action-toggle-pin-confirm-message',
      })?.text || '确定将这条讨论置顶吗？',
      confirmText: getUiCopy({
        surface: 'discussion-action-toggle-pin-confirm-confirm',
      })?.text || '置顶讨论',
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: 'primary',
    },
    order: 40
  })
})

registerDiscussionAction({
  key: 'toggle-lock',
  moduleId: 'discussions',
  order: 50,
  surfaces: ['discussion-menu'],
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-lock',
    label: getUiCopy({
      surface: 'discussion-action-toggle-lock-label',
      isLocked: discussion.is_locked,
    })?.text || (discussion.is_locked ? '解除锁定' : '锁定讨论'),
    icon: discussion.is_locked ? 'fas fa-lock-open' : 'fas fa-lock',
    description: getUiCopy({
      surface: 'discussion-action-toggle-lock-description',
      isLocked: discussion.is_locked,
    })?.text || (discussion.is_locked ? '恢复普通用户回复能力。' : '阻止普通用户继续回复。'),
    confirm: discussion.is_locked ? null : {
      title: getUiCopy({
        surface: 'discussion-action-toggle-lock-confirm-title',
      })?.text || '锁定讨论',
      message: getUiCopy({
        surface: 'discussion-action-toggle-lock-confirm-message',
      })?.text || '确定锁定当前讨论并阻止普通用户继续回复吗？',
      confirmText: getUiCopy({
        surface: 'discussion-action-toggle-lock-confirm-confirm',
      })?.text || '锁定讨论',
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: 'warning',
    },
    order: 50
  })
})

registerDiscussionAction({
  key: 'toggle-hide',
  moduleId: 'discussions',
  order: 60,
  surfaces: ['discussion-menu'],
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: ({ discussion }) => ({
    key: 'toggle-hide',
    label: getUiCopy({
      surface: 'discussion-action-toggle-hide-label',
      isHidden: discussion.is_hidden,
    })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
    icon: discussion.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
    description: getUiCopy({
      surface: 'discussion-action-toggle-hide-description',
      isHidden: discussion.is_hidden,
    })?.text || (discussion.is_hidden ? '重新让讨论出现在前台列表。' : '临时从前台列表隐藏当前讨论。'),
    confirm: {
      title: getUiCopy({
        surface: 'discussion-action-toggle-hide-confirm-title',
        isHidden: discussion.is_hidden,
      })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
      message: getUiCopy({
        surface: 'discussion-action-toggle-hide-confirm-message',
        isHidden: discussion.is_hidden,
      })?.text || (discussion.is_hidden ? '确定恢复显示当前讨论吗？' : '确定从前台列表隐藏当前讨论吗？'),
      confirmText: getUiCopy({
        surface: 'discussion-action-toggle-hide-confirm-confirm',
        isHidden: discussion.is_hidden,
      })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: discussion.is_hidden ? 'primary' : 'warning',
    },
    order: 60
  })
})

registerDiscussionAction({
  key: 'delete',
  moduleId: 'discussions',
  order: 70,
  surfaces: ['discussion-menu'],
  isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
  resolve: () => ({
    key: 'delete',
    label: getUiCopy({
      surface: 'discussion-action-delete-label',
    })?.text || '删除讨论',
    icon: 'fas fa-trash',
    description: getUiCopy({
      surface: 'discussion-action-delete-description',
    })?.text || '永久删除当前讨论及其回复。',
    tone: 'danger',
    confirm: {
      title: getUiCopy({
        surface: 'discussion-action-delete-confirm-title',
      })?.text || '删除讨论',
      message: getUiCopy({
        surface: 'discussion-action-delete-confirm-message',
      })?.text || '确定要删除这个讨论吗？此操作不可恢复。',
      confirmText: getUiCopy({
        surface: 'discussion-action-delete-confirm-confirm',
      })?.text || '删除',
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: 'danger',
    },
    order: 70
  })
})

registerPostAction({
  key: 'edit-post',
  moduleId: 'posts',
  order: 10,
  surfaces: ['post-menu'],
  isVisible: ({ post, canEditPost }) => Boolean(canEditPost(post)),
  resolve: () => ({
    key: 'edit-post',
    label: getUiCopy({
      surface: 'post-action-edit-label',
    })?.text || '编辑',
    icon: 'fas fa-pen',
    description: getUiCopy({
      surface: 'post-action-edit-description',
    })?.text || '修改这条回复内容。',
    order: 10
  })
})

registerPostAction({
  key: 'delete-post',
  moduleId: 'posts',
  order: 20,
  surfaces: ['post-menu'],
  isVisible: ({ post, canDeletePost }) => Boolean(canDeletePost(post)),
  resolve: () => ({
    key: 'delete-post',
    label: getUiCopy({
      surface: 'post-action-delete-label',
    })?.text || '删除',
    icon: 'fas fa-trash',
    description: getUiCopy({
      surface: 'post-action-delete-description',
    })?.text || '永久删除这条回复。',
    tone: 'danger',
    confirm: {
      title: getUiCopy({
        surface: 'post-action-delete-confirm-title',
      })?.text || '删除回复',
      message: getUiCopy({
        surface: 'post-action-delete-confirm-message',
      })?.text || '确定要删除这条回复吗？此操作不可恢复。',
      confirmText: getUiCopy({
        surface: 'post-action-delete-confirm-confirm',
      })?.text || '删除',
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: 'danger',
    },
    order: 20
  })
})

registerPostAction({
  key: 'toggle-hide-post',
  moduleId: 'posts',
  order: 25,
  surfaces: ['post-menu'],
  isVisible: ({ post, canModeratePostVisibility }) => Boolean(canModeratePostVisibility?.(post)),
  resolve: ({ post }) => ({
    key: 'toggle-hide-post',
    label: getUiCopy({
      surface: 'post-action-toggle-hide-label',
      isHidden: post.is_hidden,
    })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
    icon: post.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
    description: getUiCopy({
      surface: 'post-action-toggle-hide-description',
      isHidden: post.is_hidden,
    })?.text || (post.is_hidden ? '重新让这条回复在前台可见。' : '临时从前台隐藏这条回复。'),
    confirm: {
      title: getUiCopy({
        surface: 'post-action-toggle-hide-confirm-title',
        isHidden: post.is_hidden,
      })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
      message: getUiCopy({
        surface: 'post-action-toggle-hide-confirm-message',
        isHidden: post.is_hidden,
        postNumber: post.number,
      })?.text || (post.is_hidden ? `确定恢复显示 #${post.number} 吗？` : `确定隐藏 #${post.number} 吗？`),
      confirmText: getUiCopy({
        surface: 'post-action-toggle-hide-confirm-confirm',
        isHidden: post.is_hidden,
      })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
      cancelText: getUiCopy({
        surface: 'discussion-action-confirm-cancel',
      })?.text || '取消',
      tone: post.is_hidden ? 'primary' : 'warning',
    },
    order: 25
  })
})
