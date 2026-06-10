
import { api, ref } from '@bias/core'
import { runDiscussionAction } from '@bias/discussions'
import {
  useDiscussionDetailPostModerationActions } from './useDiscussionDetailPostModerationActions'

export function useDiscussionDetailModerationActions({
  canModeratePostVisibility,
  discussion,
  modalStore,
  patchDiscussion,
  refreshDiscussion,
  router,
  showActionError,
  uiText,
}) {
  const pendingDiscussionActions = ref({})
  const postModerationActions = useDiscussionDetailPostModerationActions({
    canModeratePostVisibility,
    modalStore,
    refreshDiscussion,
    showActionError,
    uiText,
  })

  async function moderateDiscussion(action) {
    if (!discussion.value) return

    return runDiscussionAction({
      key: action,
      action,
    }, {
      action,
      discussion: discussion.value,
      modalStore,
      refreshDiscussion,
      showActionError,
      uiText,
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

  function setDiscussionActionPending(action, value) {
    const key = String(action || '').trim()
    if (!key) return

    const nextPendingActions = { ...pendingDiscussionActions.value }
    if (value) {
      nextPendingActions[key] = true
    } else {
      delete nextPendingActions[key]
    }
    pendingDiscussionActions.value = nextPendingActions
  }

  function isDiscussionActionPending(action) {
    return Boolean(pendingDiscussionActions.value[String(action || '').trim()])
  }

  return {
    deleteDiscussion,
    moderateDiscussion,
    toggleHide,
    toggleLock,
    togglePin,
    isDiscussionActionPending,
    pendingDiscussionActions,
    setDiscussionActionPending,
    ...postModerationActions,
  }
}
