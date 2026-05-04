import { computed, ref } from 'vue'
import api from '@/api'
import { formatRelativeTime } from '@/utils/forum'
import ModerationActionModal from '@/components/modals/ModerationActionModal.vue'
import PostReportModal from '@/components/modals/PostReportModal.vue'

export function useDiscussionDetailInteractions({
  authStore,
  composerStore,
  discussion,
  hasActiveComposer,
  modalStore,
  posts,
  refreshDiscussion,
  route,
  router,
  scrollToPost,
  totalPosts,
  upsertPost
}) {
  const togglingSubscription = ref(false)
  const likePendingPostIds = ref([])
  const flagPendingPostIds = ref([])

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
  const canModeratePendingDiscussion = computed(() => {
    return Boolean(authStore.user?.is_staff && discussion.value?.approval_status === 'pending')
  })
  const suspensionNotice = computed(() => {
    if (!isSuspended.value) return ''

    const user = authStore.user || {}
    if (user.suspend_message) {
      return user.suspended_until
        ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}。${user.suspend_message}`
        : `账号当前已被封禁。${user.suspend_message}`
    }

    return user.suspended_until
      ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}，暂时无法回复、点赞、举报或关注讨论。`
      : '账号当前已被封禁，暂时无法回复、点赞、举报或关注讨论。'
  })

  function getUiErrorMessage(error, fallback = '操作失败，请稍后重试') {
    return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
  }

  function showSuspensionAlert() {
    return modalStore.alert({
      title: '账号已被封禁',
      message: suspensionNotice.value,
      tone: 'danger'
    })
  }

  async function toggleLike(post) {
    if (!authStore.isAuthenticated) {
      router.push('/login')
      return
    }
    if (!canLikePost(post)) {
      return
    }
    if (isSuspended.value) {
      await showSuspensionAlert()
      return
    }
    if (likePendingPostIds.value.includes(post.id)) {
      return
    }

    likePendingPostIds.value.push(post.id)
    const previousLiked = Boolean(post.is_liked)
    const previousLikeCount = Number(post.like_count || 0)
    try {
      if (previousLiked) {
        post.like_count = Math.max(0, previousLikeCount - 1)
        post.is_liked = false
        await api.delete(`/posts/${post.id}/like`)
      } else {
        post.like_count = previousLikeCount + 1
        post.is_liked = true
        await api.post(`/posts/${post.id}/like`)
      }
    } catch (error) {
      post.like_count = previousLikeCount
      post.is_liked = previousLiked
      console.error('点赞失败:', error)
      await modalStore.alert({
        title: '点赞失败',
        message: getUiErrorMessage(error, '请稍后重试'),
        tone: 'danger'
      })
    } finally {
      likePendingPostIds.value = likePendingPostIds.value.filter(id => id !== post.id)
    }
  }

  function replyToPost(post) {
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }
    composerStore.openReplyComposer({
      source: 'discussion-detail',
      discussionId: discussion.value?.id,
      discussionTitle: discussion.value?.title || '',
      postId: post.id,
      postNumber: post.number,
      username: post.user.username,
      initialContent: `@${post.user.username} `
    })
  }

  function editPost(post) {
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }
    composerStore.openEditPostComposer({
      source: 'discussion-detail',
      discussionId: discussion.value?.id,
      discussionTitle: discussion.value?.title || '',
      postId: post.id,
      postNumber: post.number,
      username: post.user.username,
      initialContent: post.content
    })
  }

  function editDiscussion() {
    if (!discussion.value || !canEditDiscussion.value) return
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }

    const primaryTag = (discussion.value.tags || []).find(tag => !tag.parent_id)
    const secondaryTag = (discussion.value.tags || []).find(tag => tag.parent_id)

    composerStore.openEditDiscussionComposer({
      source: 'discussion-detail',
      discussionId: discussion.value.id,
      discussionTitle: discussion.value.title || '',
      initialTitle: discussion.value.title || '',
      initialContent: discussion.value.first_post?.content || '',
      initialPrimaryTagId: primaryTag?.id || '',
      initialSecondaryTagId: secondaryTag?.id || ''
    })
  }

  function openComposer() {
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }
    if (hasActiveComposer.value) {
      composerStore.showComposer()
      return
    }

    composerStore.openReplyComposer({
      source: 'discussion-detail',
      discussionId: discussion.value?.id,
      discussionTitle: discussion.value?.title || '',
      postId: null,
      postNumber: null,
      username: '',
      initialContent: ''
    })
  }

  function goToLoginForReply() {
    router.push({
      name: 'login',
      query: {
        redirect: route.fullPath
      }
    })
  }

  async function deletePost(post) {
    const confirmed = await modalStore.confirm({
      title: '删除回复',
      message: '确定要删除这条回复吗？',
      confirmText: '删除',
      cancelText: '取消',
      tone: 'danger'
    })
    if (!confirmed) return

    try {
      await api.delete(`/posts/${post.id}`)
      posts.value = posts.value.filter(item => item.id !== post.id)
      discussion.value.comment_count--
      totalPosts.value = Math.max(0, totalPosts.value - 1)
    } catch (error) {
      console.error('删除失败:', error)
      await modalStore.alert({
        title: '删除失败',
        message: '请稍后重试',
        tone: 'danger'
      })
    }
  }

  function canEditPost(post) {
    if (isSuspended.value) return false
    return authStore.user?.id === post.user.id || authStore.user?.is_staff
  }

  function canDeletePost(post) {
    if (isSuspended.value) return false
    return authStore.user?.id === post.user.id || authStore.user?.is_staff
  }

  function canLikePost(post) {
    if (!authStore.isAuthenticated) return false
    if (isSuspended.value) return false
    return Boolean(post?.can_like ?? (post?.user?.id !== authStore.user?.id))
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

  function canModeratePendingPost(post) {
    return Boolean(authStore.user?.is_staff && post?.approval_status === 'pending')
  }

  async function moderateDiscussion(action) {
    if (!discussion.value || !canModeratePendingDiscussion.value) return

    const isApprove = action === 'approve'
    const result = await modalStore.show(
      ModerationActionModal,
      {
        title: isApprove ? '审核通过讨论' : '拒绝讨论',
        description: isApprove
          ? '通过后，这条讨论会立即对其他用户可见。'
          : '拒绝后，讨论作者仍可在前台看到你的审核反馈。',
        confirmText: isApprove ? '通过审核' : '确认拒绝',
        confirmTone: isApprove ? 'primary' : 'danger',
        placeholder: isApprove ? '例如：内容符合社区规范，已放行' : '例如：标题与正文需要补充后再发布',
        submitAction: ({ note }) => api.post(
          `/admin/approval-queue/discussion/${discussion.value.id}/${action}`,
          { note }
        )
      },
      {
        size: 'small'
      }
    )

    if (!result) return
    await refreshDiscussion()
    await modalStore.alert({
      title: isApprove ? '讨论已通过' : '讨论已拒绝',
      message: isApprove ? '这条讨论现在已经对其他用户可见。' : '作者现在可以在前台看到你的审核反馈。'
    })
  }

  async function moderatePost(post, action) {
    if (!post || !canModeratePendingPost(post)) return

    const isApprove = action === 'approve'
    const result = await modalStore.show(
      ModerationActionModal,
      {
        title: isApprove ? `审核通过 #${post.number}` : `拒绝 #${post.number}`,
        description: isApprove
          ? '通过后，这条回复会立刻出现在讨论流中。'
          : '拒绝后，回复作者仍可在前台看到你的审核反馈。',
        confirmText: isApprove ? '通过审核' : '确认拒绝',
        confirmTone: isApprove ? 'primary' : 'danger',
        placeholder: isApprove ? '例如：内容符合社区规范，已放行' : '例如：回复缺少上下文，请补充后重新提交',
        submitAction: ({ note }) => api.post(
          `/admin/approval-queue/post/${post.id}/${action}`,
          { note }
        )
      },
      {
        size: 'small'
      }
    )

    if (!result) return
    await refreshDiscussion()
    await modalStore.alert({
      title: isApprove ? '回复已通过' : '回复已拒绝',
      message: isApprove ? '这条回复现在已经加入讨论流。' : '作者现在可以在前台看到你的审核反馈。'
    })
  }

  async function togglePostHidden(post) {
    if (!canModeratePostVisibility(post)) return

    const nextActionLabel = post.is_hidden ? '恢复显示' : '隐藏回复'
    const confirmed = await modalStore.confirm({
      title: nextActionLabel,
      message: post.is_hidden ? `确定恢复显示 #${post.number} 吗？` : `确定隐藏 #${post.number} 吗？`,
      confirmText: nextActionLabel,
      cancelText: '取消',
      tone: post.is_hidden ? 'primary' : 'warning'
    })
    if (!confirmed) return

    try {
      await api.post(`/posts/${post.id}/hide`)
      await refreshDiscussion()
    } catch (error) {
      console.error('切换回复隐藏状态失败:', error)
      await modalStore.alert({
        title: '操作失败',
        message: getUiErrorMessage(error, '请稍后重试'),
        tone: 'danger'
      })
    }
  }

  async function openReportModal(post) {
    if (isSuspended.value) {
      await showSuspensionAlert()
      return
    }

    try {
      const result = await modalStore.show(
        PostReportModal,
        {
          post,
          submitReport: payload => api.post(`/posts/${post.id}/report`, payload)
        },
        {
          size: 'small'
        }
      )

      if (result?.reported) {
        post.viewer_has_open_flag = true
        await modalStore.alert({
          title: '举报已提交',
          message: '版主会尽快查看并处理。'
        })
      }
    } catch (error) {
      console.error('举报失败:', error)
      await modalStore.alert({
        title: '举报失败',
        message: getUiErrorMessage(error, '请稍后重试'),
        tone: 'danger'
      })
    }
  }

  async function resolvePostFlags(post, status) {
    if (!post?.can_moderate_flags) return
    if (flagPendingPostIds.value.includes(post.id)) return

    const isIgnoring = status === 'ignored'
    const confirmed = await modalStore.confirm({
      title: isIgnoring ? '忽略举报' : '处理举报',
      message: isIgnoring
        ? `确定忽略这条回复的 ${post.open_flag_count} 条举报吗？`
        : `确定将这条回复的 ${post.open_flag_count} 条举报标记为已处理吗？`,
      confirmText: isIgnoring ? '忽略' : '已处理',
      cancelText: '取消',
      tone: isIgnoring ? 'warning' : 'primary'
    })
    if (!confirmed) return

    flagPendingPostIds.value.push(post.id)
    try {
      const response = await api.post(`/posts/${post.id}/flags/resolve`, {
        status,
        resolution_note: ''
      })
      if (response?.post) {
        upsertPost(response.post)
      }
      await modalStore.alert({
        title: isIgnoring ? '举报已忽略' : '举报已处理',
        message: isIgnoring ? '这条回复的待处理举报已关闭。' : '这条回复的待处理举报已标记为已处理。'
      })
    } catch (error) {
      console.error('处理举报失败:', error)
      await modalStore.alert({
        title: '处理举报失败',
        message: getUiErrorMessage(error, '请稍后重试'),
        tone: 'danger'
      })
    } finally {
      flagPendingPostIds.value = flagPendingPostIds.value.filter(id => id !== post.id)
    }
  }

  async function togglePin() {
    try {
      await api.post(`/discussions/${discussion.value.id}/pin`)
      discussion.value.is_sticky = !discussion.value.is_sticky
    } catch (error) {
      console.error('操作失败:', error)
    }
  }

  async function toggleLock() {
    try {
      await api.post(`/discussions/${discussion.value.id}/lock`)
      discussion.value.is_locked = !discussion.value.is_locked
    } catch (error) {
      console.error('操作失败:', error)
    }
  }

  async function toggleHide() {
    try {
      await api.post(`/discussions/${discussion.value.id}/hide`)
      discussion.value.is_hidden = !discussion.value.is_hidden
    } catch (error) {
      console.error('操作失败:', error)
    }
  }

  async function deleteDiscussion() {
    const confirmed = await modalStore.confirm({
      title: '删除讨论',
      message: '确定要删除这个讨论吗？此操作不可恢复！',
      confirmText: '删除',
      cancelText: '取消',
      tone: 'danger'
    })
    if (!confirmed) return

    try {
      await api.delete(`/discussions/${discussion.value.id}`)
      router.push('/')
    } catch (error) {
      console.error('删除失败:', error)
      await modalStore.alert({
        title: '删除失败',
        message: '请稍后重试',
        tone: 'danger'
      })
    }
  }

  async function toggleSubscription() {
    if (!authStore.isAuthenticated || !discussion.value) {
      router.push('/login')
      return
    }
    if (isSuspended.value) {
      await showSuspensionAlert()
      return
    }

    togglingSubscription.value = true
    try {
      if (discussion.value.is_subscribed) {
        await api.delete(`/discussions/${discussion.value.id}/subscribe`)
        discussion.value.is_subscribed = false
      } else {
        await api.post(`/discussions/${discussion.value.id}/subscribe`)
        discussion.value.is_subscribed = true
      }
    } catch (error) {
      console.error('更新关注状态失败:', error)
      await modalStore.alert({
        title: '更新关注失败',
        message: getUiErrorMessage(error, '请稍后重试'),
        tone: 'danger'
      })
    } finally {
      togglingSubscription.value = false
    }
  }

  function formatDate(dateString) {
    return formatRelativeTime(dateString)
  }

  function formatLikeSummary(post) {
    const count = Number(post?.like_count || 0)
    if (count <= 0) return ''

    if (post?.is_liked) {
      return count === 1 ? '你赞了这条回复' : `你和其他 ${count - 1} 人赞了这条回复`
    }

    return `${count} 人赞了这条回复`
  }

  function formatAbsoluteDate(value) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '未知时间'
    return date.toLocaleString('zh-CN')
  }

  return {
    canDeletePost,
    canEditDiscussion,
    canEditPost,
    canLikePost,
    canModerateDiscussionSettings,
    canModeratePostVisibility,
    canModeratePendingDiscussion,
    canModeratePendingPost,
    canReplyFromMenu,
    canReportPost,
    canShowDiscussionMenu,
    deleteDiscussion,
    deletePost,
    editDiscussion,
    editPost,
    flagPendingPostIds,
    formatAbsoluteDate,
    formatDate,
    formatLikeSummary,
    goToLoginForReply,
    isSuspended,
    likePendingPostIds,
    moderateDiscussion,
    moderatePost,
    openComposer,
    openReportModal,
    replyToPost,
    resolvePostFlags,
    showSuspensionAlert,
    suspensionNotice,
    toggleHide,
    toggleLike,
    toggleLock,
    togglePin,
    togglePostHidden,
    toggleSubscription,
    togglingSubscription
  }
}
