import { ref } from 'vue'
import api from '@/api'
import { getUiCopy } from '@/forum/registry'
import { useResourceStore } from '@/stores/resource'
import { buildDiscussionPath, formatRelativeTime } from '@/utils/forum'

export function useDiscussionDetailUserActions({
  authStore,
  canEditDiscussion,
  canLikePost,
  composerStore,
  discussion,
  hasActiveComposer,
  isSuspended,
  modalStore,
  patchDiscussion,
  refreshDiscussion,
  removePost,
  route,
  router,
  suspensionNotice,
  totalPosts,
}) {
  const resourceStore = useResourceStore()
  const likePendingPostIds = ref([])

  function uiText(surface, fallback, context = {}) {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  function getUiErrorMessage(error, fallback = uiText('discussion-detail-action-retry-message', '请稍后重试')) {
    return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
  }

  async function showActionError(actionLabel, error, fallback = uiText('discussion-detail-action-retry-message', '请稍后重试')) {
    await modalStore.alert({
      title: uiText('discussion-detail-action-error-title', '操作失败', { actionLabel }),
      message: getUiErrorMessage(error, fallback),
      tone: 'danger'
    })
  }

  function showSuspensionAlert() {
    return modalStore.alert({
      title: uiText('discussion-detail-suspension-alert-title', '账号已被封禁'),
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
        resourceStore.patch('posts', post.id, {
          like_count: Math.max(0, previousLikeCount - 1),
          is_liked: false,
        })
        await api.delete(`/posts/${post.id}/like`)
      } else {
        resourceStore.patch('posts', post.id, {
          like_count: previousLikeCount + 1,
          is_liked: true,
        })
        await api.post(`/posts/${post.id}/like`)
      }
    } catch (error) {
      resourceStore.patch('posts', post.id, {
        like_count: previousLikeCount,
        is_liked: previousLiked,
      })
      console.error('点赞失败:', error)
      await showActionError('点赞', error)
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
      approvalStatus: post.approval_status || '',
      approvalNote: post.approval_note || '',
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
      approvalStatus: discussion.value.approval_status || '',
      approvalNote: discussion.value.approval_note || '',
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

  async function shareDiscussion() {
    if (!discussion.value) return

    const path = buildDiscussionPath(discussion.value)
    const href = typeof window === 'undefined'
      ? path
      : new URL(path, window.location.origin).toString()

    try {
      if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
        await navigator.share({
          title: discussion.value.title || uiText('discussion-detail-share-title', '讨论'),
          url: href,
        })
        return
      }

      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(href)
        await modalStore.alert({
          title: uiText('discussion-detail-share-copied-title', '链接已复制'),
          message: uiText('discussion-detail-share-copied-message', '讨论链接已复制到剪贴板。')
        })
        return
      }

      await modalStore.alert({
        title: uiText('discussion-detail-share-manual-title', '分享讨论'),
        message: href
      })
    } catch (error) {
      if (error?.name === 'AbortError') return
      console.error('分享讨论失败:', error)
      await showActionError('分享讨论', error, uiText('discussion-detail-share-fallback', '请稍后重试'))
    }
  }

  async function deletePost(post) {
    try {
      await api.delete(`/posts/${post.id}`)
      removePost(post.id)
      const shouldRefreshDiscussion = Number(post?.number || 0) >= Number(discussion.value?.last_post_number || 0)

      patchDiscussion(currentDiscussion => ({
        comment_count: Math.max(0, Number(currentDiscussion.comment_count || 0) - 1),
      }))
      totalPosts.value = Math.max(0, totalPosts.value - 1)

      if (shouldRefreshDiscussion) {
        await refreshDiscussion()
      }
    } catch (error) {
      console.error('删除失败:', error)
      await showActionError('删除', error)
    }
  }

  function formatDate(dateString) {
    return formatRelativeTime(dateString)
  }

  function formatLikeSummary(post) {
    const count = Number(post?.like_count || 0)
    return uiText('discussion-detail-like-summary', '', {
      count,
      isLiked: Boolean(post?.is_liked),
    })
  }

  return {
    deletePost,
    editDiscussion,
    editPost,
    formatDate,
    formatLikeSummary,
    goToLoginForReply,
    likePendingPostIds,
    openComposer,
    replyToPost,
    shareDiscussion,
    showActionError,
    showSuspensionAlert,
    toggleLike,
    uiText,
  }
}
