export function getPostOpenFlagCount(post) {
  return Number(post?.open_flag_count || 0)
}

export function hasViewerOpenFlag(post) {
  return Boolean(post?.viewer_has_open_flag)
}

export function canModeratePostFlags(post) {
  return Boolean(post?.can_moderate_flags)
}

export function normalizePostFlag(flag) {
  const item = flag && typeof flag === 'object' ? flag : {}
  return {
    key: item.id,
    reason: item.reason,
    userLabel: item.user?.display_name || item.user?.username || '匿名用户',
    message: item.message || '举报人未填写补充说明。',
  }
}

export function buildPostFlagPanel(post) {
  const flagPending = Boolean(post?.is_flag_pending)
  return {
    title: '前台举报处理',
    description: '版主可直接在这里查看原因并关闭举报。',
    items: (post?.open_flags || []).map(normalizePostFlag),
    actions: [
      {
        key: 'resolved',
        action: 'resolve-post-flags',
        label: flagPending ? '处理中...' : '标记已处理',
        tone: 'primary',
        status: 'resolved',
        disabled: flagPending,
      },
      {
        key: 'ignored',
        action: 'resolve-post-flags',
        label: '忽略举报',
        tone: 'secondary',
        status: 'ignored',
        disabled: flagPending,
      },
    ],
  }
}
