import { ref } from 'vue'
import api from '@/api'
import ModerationActionModal from '@/components/modals/ModerationActionModal.vue'

export function useDiscussionDetailPostModerationActions({
  canModeratePendingPost,
  canModeratePostVisibility,
  modalStore,
  refreshDiscussion,
  showActionError,
  uiText,
}) {

  async function moderatePost(post, action) {
    if (!post || !canModeratePendingPost(post)) return

    const isApprove = action === 'approve'
    const result = await modalStore.show(
      ModerationActionModal,
      {
        title: uiText(
          'discussion-detail-moderation-title',
          isApprove ? `审核通过 #${post.number}` : `拒绝 #${post.number}`,
          { action, postNumber: post.number, targetType: 'post' }
        ),
        description: uiText(
          'discussion-detail-moderation-description',
          isApprove ? '通过后，这条回复会立刻出现在讨论流中。' : '拒绝后，回复作者仍可在前台看到你的审核反馈。',
          { action, postNumber: post.number, targetType: 'post' }
        ),
        confirmText: uiText(
          'discussion-detail-moderation-confirm',
          isApprove ? '通过审核' : '确认拒绝',
          { action, postNumber: post.number, targetType: 'post' }
        ),
        confirmTone: isApprove ? 'primary' : 'danger',
        placeholder: uiText(
          'discussion-detail-moderation-placeholder',
          isApprove ? '例如：内容符合社区规范，已放行' : '例如：回复缺少上下文，请补充后重新提交',
          { action, postNumber: post.number, targetType: 'post' }
        ),
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
      title: uiText(
        'discussion-detail-moderation-success-title',
        isApprove ? '回复已通过' : '回复已拒绝',
        { action, postNumber: post.number, targetType: 'post' }
      ),
      message: uiText(
        'discussion-detail-moderation-success-message',
        isApprove ? '这条回复现在已经加入讨论流。' : '作者现在可以在前台看到你的审核反馈。',
        { action, postNumber: post.number, targetType: 'post' }
      )
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
