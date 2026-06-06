import { Forum } from '@bias/forum'
import {
  PostReportModal,
  forumApi,
  getUiCopy,
} from '@/forum/registry'

export const extend = [
  buildFlagsForumExtender(),
]

function buildFlagsForumExtender() {
  const forum = new Forum()
  registerFlagsForum(forum)
  return forum
}

function registerFlagsForum(forum) {
  forum.postAction({
    key: 'open-report-modal',
    moduleId: 'flags',
    order: 30,
    isVisible: ({ post, canReportPost }) => Boolean(canReportPost(post)),
    resolve: () => ({
      key: 'open-report-modal',
      label: getUiCopy({ surface: 'post-action-report-label' })?.text || '举报',
      icon: 'fas fa-flag',
      description: getUiCopy({ surface: 'post-action-report-description' })?.text || '向版主提交这条回复的问题反馈。',
      order: 30,
    }),
  })

  forum.postActionHandler({
    key: 'open-report-modal',
    moduleId: 'flags',
    order: 10,
    handle: handleOpenReportModal,
  })

  forum.postActionHandler({
    key: 'resolve-post-flags',
    moduleId: 'flags',
    order: 10,
    isVisible: ({ post }) => Boolean(post?.can_moderate_flags),
    handle: handleResolvePostFlags,
  })

  forum.postStateBadge({
    key: 'viewer-open-flag',
    moduleId: 'flags',
    order: 30,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => Boolean(post?.viewer_has_open_flag && !post?.can_moderate_flags),
    resolve: () => ({
      label: '已举报',
      tone: 'info',
    }),
  })

  forum.postStateBadge({
    key: 'open-flags',
    moduleId: 'flags',
    order: 40,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => Boolean(Number(post?.open_flag_count || 0) > 0 && post?.can_moderate_flags),
    resolve: ({ post }) => ({
      label: `${post.open_flag_count} 条举报待处理`,
      tone: 'soft-warning',
    }),
  })

  forum.postFlagPanel({
    key: 'moderation-flags',
    moduleId: 'flags',
    order: 10,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => Boolean(post?.can_moderate_flags && Number(post?.open_flag_count || 0) > 0),
    resolve: ({ post, flagPending }) => ({
      title: '前台举报处理',
      description: '版主可直接在这里查看原因并关闭举报。',
      items: (post.open_flags || []).map(flag => ({
        key: flag.id,
        reason: flag.reason,
        userLabel: flag.user?.display_name || flag.user?.username || '匿名用户',
        message: flag.message || '举报人未填写补充说明。',
      })),
      actions: [
        {
          key: 'resolved',
          label: flagPending ? '处理中...' : '标记已处理',
          tone: 'primary',
          status: 'resolved',
          disabled: Boolean(flagPending),
        },
        {
          key: 'ignored',
          label: '忽略举报',
          tone: 'secondary',
          status: 'ignored',
          disabled: Boolean(flagPending),
        },
      ],
    }),
  })

  registerFlagsUiCopy(forum)
}

async function handleOpenReportModal({
  isSuspended,
  modalStore,
  patchPost,
  post,
  showActionError,
  showSuspensionAlert,
  uiText,
}) {
  if (!post) return
  if (isSuspended) {
    await showSuspensionAlert?.()
    return
  }

  try {
    const result = await modalStore.show(
      PostReportModal,
      {
        post,
        submitReport: payload => forumApi.post(`/posts/${post.id}/report`, payload),
      },
      { size: 'small' }
    )

    if (!result?.reported) return
    patchPost?.(post.id, { viewer_has_open_flag: true })
    await modalStore.alert({
      title: resolveText(uiText, 'discussion-detail-report-success-title', '举报已提交'),
      message: resolveText(uiText, 'discussion-detail-report-success-message', '版主会尽快查看并处理。'),
    })
  } catch (error) {
    console.error('提交举报失败:', error)
    await showActionError?.('举报', error)
  }
}

async function handleResolvePostFlags({
  modalStore,
  patchPost,
  post,
  showActionError,
  status,
  uiText,
  upsertPost,
}) {
  if (!post?.can_moderate_flags) return

  const isIgnoring = status === 'ignored'
  const openFlagCount = Number(post.open_flag_count || 0)
  const confirmed = await modalStore.confirm({
    title: resolveText(
      uiText,
      'discussion-detail-flag-resolve-confirm-title',
      isIgnoring ? '忽略举报' : '处理举报',
      { isIgnoring, openFlagCount }
    ),
    message: resolveText(
      uiText,
      'discussion-detail-flag-resolve-confirm-message',
      isIgnoring
        ? `确定忽略这条回复的 ${openFlagCount} 条举报吗？`
        : `确定将这条回复的 ${openFlagCount} 条举报标记为已处理吗？`,
      { isIgnoring, openFlagCount }
    ),
    confirmText: resolveText(
      uiText,
      'discussion-detail-flag-resolve-confirm-confirm',
      isIgnoring ? '忽略' : '已处理',
      { isIgnoring, openFlagCount }
    ),
    cancelText: resolveText(uiText, 'discussion-action-confirm-cancel', '取消'),
    tone: isIgnoring ? 'warning' : 'primary',
  })
  if (!confirmed) return

  patchPost?.(post.id, { is_flag_pending: true })
  try {
    const response = await forumApi.post(`/posts/${post.id}/flags/resolve`, { status })
    if (response?.post) {
      upsertPost?.({
        ...response.post,
        is_flag_pending: false,
      })
    } else {
      patchPost?.(post.id, {
        is_flag_pending: false,
        open_flag_count: 0,
        open_flags: [],
      })
    }
    await modalStore.alert({
      title: resolveText(
        uiText,
        'discussion-detail-flag-resolve-success-title',
        isIgnoring ? '举报已忽略' : '举报已处理',
        { isIgnoring, openFlagCount }
      ),
      message: resolveText(
        uiText,
        'discussion-detail-flag-resolve-success-message',
        isIgnoring ? '这条回复的待处理举报已关闭。' : '这条回复的待处理举报已标记为已处理。',
        { isIgnoring, openFlagCount }
      ),
    })
  } catch (error) {
    patchPost?.(post.id, { is_flag_pending: false })
    console.error('处理举报失败:', error)
    await showActionError?.('处理举报', error)
  }
}

function resolveText(uiText, surface, fallback, context = {}) {
  return typeof uiText === 'function' ? uiText(surface, fallback, context) : fallback
}

function registerFlagsUiCopy(forum) {
  forum.uiCopy({
    key: 'post-action-report-label',
    moduleId: 'flags',
    order: 479,
    surfaces: ['post-action-report-label'],
    resolve: () => ({ text: '举报' }),
  })

  forum.uiCopy({
    key: 'post-action-report-description',
    moduleId: 'flags',
    order: 479,
    surfaces: ['post-action-report-description'],
    resolve: () => ({ text: '向版主提交这条回复的问题反馈。' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-report-success-title',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-report-success-title'],
    resolve: () => ({ text: '举报已提交' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-report-success-message',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-report-success-message'],
    resolve: () => ({ text: '版主会尽快查看并处理。' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-flag-resolve-confirm-title',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-flag-resolve-confirm-title'],
    resolve: ({ isIgnoring }) => ({ text: isIgnoring ? '忽略举报' : '处理举报' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-flag-resolve-confirm-message',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-flag-resolve-confirm-message'],
    resolve: ({ isIgnoring, openFlagCount }) => ({
      text: isIgnoring
        ? `确定忽略这条回复的 ${openFlagCount} 条举报吗？`
        : `确定将这条回复的 ${openFlagCount} 条举报标记为已处理吗？`,
    }),
  })

  forum.uiCopy({
    key: 'discussion-detail-flag-resolve-confirm-confirm',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-flag-resolve-confirm-confirm'],
    resolve: ({ isIgnoring }) => ({ text: isIgnoring ? '忽略' : '已处理' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-flag-resolve-success-title',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-flag-resolve-success-title'],
    resolve: ({ isIgnoring }) => ({ text: isIgnoring ? '举报已忽略' : '举报已处理' }),
  })

  forum.uiCopy({
    key: 'discussion-detail-flag-resolve-success-message',
    moduleId: 'flags',
    order: 479,
    surfaces: ['discussion-detail-flag-resolve-success-message'],
    resolve: ({ isIgnoring }) => ({
      text: isIgnoring ? '这条回复的待处理举报已关闭。' : '这条回复的待处理举报已标记为已处理。',
    }),
  })

  forum.uiCopy({
    key: 'post-report-title',
    moduleId: 'flags',
    order: 840,
    surfaces: ['post-report-title'],
    resolve: () => ({ text: '举报帖子' }),
  })

  forum.uiCopy({
    key: 'post-report-description',
    moduleId: 'flags',
    order: 850,
    surfaces: ['post-report-description'],
    resolve: ({ postNumber }) => ({
      text: `帖子 #${postNumber || '?'} 会进入举报队列，版主可以直接在讨论页或后台查看并处理。`,
    }),
  })

  forum.uiCopy({
    key: 'post-report-reason-label',
    moduleId: 'flags',
    order: 860,
    surfaces: ['post-report-reason-label'],
    resolve: () => ({ text: '举报原因' }),
  })

  forum.uiCopy({
    key: 'post-report-message-label',
    moduleId: 'flags',
    order: 870,
    surfaces: ['post-report-message-label'],
    resolve: () => ({ text: '补充说明' }),
  })

  forum.uiCopy({
    key: 'post-report-message-help',
    moduleId: 'flags',
    order: 880,
    surfaces: ['post-report-message-help'],
    resolve: ({ reason }) => ({
      text: reason === '其他' ? '请尽量写清楚问题背景，方便版主快速判断。' : '可补充上下文、受影响内容或希望的处理方式。',
    }),
  })

  forum.uiCopy({
    key: 'post-report-message-placeholder',
    moduleId: 'flags',
    order: 890,
    surfaces: ['post-report-message-placeholder'],
    resolve: () => ({ text: '告诉管理员这条帖子为什么需要处理' }),
  })

  forum.uiCopy({
    key: 'post-report-submit-button',
    moduleId: 'flags',
    order: 900,
    surfaces: ['post-report-submit-button'],
    resolve: ({ submitting }) => ({ text: submitting ? '提交中...' : '提交举报' }),
  })
}
