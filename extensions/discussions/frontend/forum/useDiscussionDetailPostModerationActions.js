import { api as api } from '@bias/core'

import { runPostAction } from '@bias/posts'

export function useDiscussionDetailPostModerationActions({
  canModeratePostVisibility,
  modalStore,
  refreshDiscussion,
  showActionError,
  uiText,
}) {

  async function moderatePost(post, action) {
    if (!post) return

    return runPostAction({
      key: action,
      action,
    }, {
      action,
      modalStore,
      post,
      refreshDiscussion,
      showActionError,
      uiText,
    })
  }

  async function togglePostHidden(post) {
    if (!canModeratePostVisibility(post)) return

    try {
      await api.post(`/posts/${post.id}/hide`)
      await refreshDiscussion()
    } catch (error) {
      console.error('切换回复隐藏状态失败:', error)
      await showActionError('切换回复隐藏状态', error)
    }
  }

  return {
    moderatePost,
    togglePostHidden,
  }
}
