import { ref } from 'vue'
import api from '@/api'
import ModerationActionModal from '@/components/modals/ModerationActionModal.vue'
import { useDiscussionDetailPostModerationActions } from '@/composables/useDiscussionDetailPostModerationActions'

export function useDiscussionDetailModerationActions({
  canModeratePendingDiscussion,
  canModeratePendingPost,
  canModeratePostVisibility,
  discussion,
  modalStore,
  patchDiscussion,
  refreshDiscussion,
  router,
  showActionError,
  uiText,
  upsertPost,
}) {
  const togglingSubscription = ref(false)
  const postModerationActions = useDiscussionDetailPostModerationActions({
    canModeratePendingPost,
    canModeratePostVisibility,
    modalStore,
    refreshDiscussion,
    showActionError,
    uiText,
  })

  async function moderateDiscussion(action) {
    if (!discussion.value || !canModeratePendingDiscussion.value) return

    const isApprove = action === 'approve'
    const result = await modalStore.show(
      ModerationActionModal,
      {
        title: uiText(
          'discussion-detail-moderation-title',
          isApprove ? '审核通过讨论' : '拒绝讨论',
          { action, targetType: 'discussion' }
        ),
        description: uiText(
          'discussion-detail-moderation-description',
          isApprove ? '通过后，这条讨论会立即对其他用户可见。' : '拒绝后，讨论作者仍可在前台看到你的审核反馈。',
          { action, targetType: 'discussion' }
        ),
        confirmText: uiText(
          'discussion-detail-moderation-confirm',
          isApprove ? '通过审核' : '确认拒绝',
          { action, targetType: 'discussion' }
        ),
        confirmTone: isApprove ? 'primary' : 'danger',
        placeholder: uiText(
          'discussion-detail-moderation-placeholder',
          isApprove ? '例如：内容符合社区规范，已放行' : '例如：标题与正文需要补充后再发布',
          { action, targetType: 'discussion' }
        ),
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
      title: uiText(
        'discussion-detail-moderation-success-title',
        isApprove ? '讨论已通过' : '讨论已拒绝',
        { action, targetType: 'discussion' }
      ),
      message: uiText(
        'discussion-detail-moderation-success-message',
        isApprove ? '这条讨论现在已经对其他用户可见。' : '作者现在可以在前台看到你的审核反馈。',
        { action, targetType: 'discussion' }
      )
    })
  }

  async function togglePin() {
    try {
      await api.post(`/discussions/${discussion.value.id}/pin`)
      patchDiscussion(currentDiscussion => ({
        is_sticky: !currentDiscussion.is_sticky,
      }))
    } catch (error) {
      console.error('操作失败:', error)
      await showActionError('更新讨论置顶状态', error)
    }
  }

  async function toggleLock() {
    try {
      await api.post(`/discussions/${discussion.value.id}/lock`)
      patchDiscussion(currentDiscussion => ({
        is_locked: !currentDiscussion.is_locked,
      }))
    } catch (error) {
      console.error('操作失败:', error)
      await showActionError('更新讨论锁定状态', error)
    }
  }

  async function toggleHide() {
    try {
      await api.post(`/discussions/${discussion.value.id}/hide`)
      patchDiscussion(currentDiscussion => ({
        is_hidden: !currentDiscussion.is_hidden,
      }))
    } catch (error) {
      console.error('操作失败:', error)
      await showActionError('更新讨论隐藏状态', error)
    }
  }

  async function deleteDiscussion() {
    try {
      await api.delete(`/discussions/${discussion.value.id}`)
      router.push('/')
    } catch (error) {
      console.error('删除失败:', error)
      await showActionError('删除', error)
    }
  }

  function setTogglingSubscription(value) {
    togglingSubscription.value = Boolean(value)
  }

  return {
    deleteDiscussion,
    moderateDiscussion,
    toggleHide,
    toggleLock,
    togglePin,
    setTogglingSubscription,
    togglingSubscription,
    ...postModerationActions,
  }
}
