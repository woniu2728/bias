import {
  api,
  formatRelativeTime } from '@bias/core'
import {
  getUiCopy,
  runComposerInitialStateContributors
} from '@bias/forum'
import { buildDiscussionPath } from '@bias/discussions'

export function useDiscussionDetailUserActions({
  authStore,
  canEditDiscussion,
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

  async function editPost(post) {
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }

    const initialState = await runComposerInitialStateContributors({
      source: 'discussion-detail',
      discussionId: discussion.value?.id,
      discussionTitle: discussion.value?.title || '',
      postId: post.id,
      postNumber: post.number,
      username: post.user.username,
      initialContent: post.content,
      extensions: {},
    }, {
      discussion: discussion.value,
      mode: 'edit',
      post,
      source: 'discussion-detail',
      submitKind: 'edit-post',
      type: 'post',
    })

    composerStore.openEditPostComposer(initialState)
  }

  async function editDiscussion() {
    if (!discussion.value || !canEditDiscussion.value) return
    if (isSuspended.value) {
      showSuspensionAlert()
      return
    }

    const initialState = await runComposerInitialStateContributors({
      source: 'discussion-detail',
      discussionId: discussion.value.id,
      discussionTitle: discussion.value.title || '',
      initialTitle: discussion.value.title || '',
      initialContent: discussion.value.first_post?.content || '',
      extensions: {},
    }, {
      discussion: discussion.value,
      mode: 'edit',
      source: 'discussion-detail',
      submitKind: 'edit-discussion',
      type: 'discussion',
    })

    composerStore.openEditDiscussionComposer(initialState)
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

  return {
    deletePost,
    editDiscussion,
    editPost,
    formatDate,
    goToLoginForReply,
    openComposer,
    replyToPost,
    shareDiscussion,
    showActionError,
    showSuspensionAlert,
    uiText,
  }
}
