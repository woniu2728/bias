import { computed } from 'vue'
import { runDiscussionAction, runPostAction } from '@/forum/registry'
import { getDiscussionMenuItems, getPostMenuItems } from '@/forum/discussionActions'

export function useDiscussionDetailMenus({
  activePostMenuId,
  authStore,
  canDeletePost,
  canEditPost,
  canModeratePostVisibility,
  canReportPost,
  canEditDiscussion,
  canModerateDiscussionSettings,
  canReplyFromMenu,
  discussion,
  hasActiveComposer,
  isSuspended,
  showDiscussionMenu,
  togglingSubscription,
  discussionActionHandlers,
  postActionHandlers,
  modalStore,
  patchDiscussion,
  setTogglingSubscription,
  showActionError,
  showSuspensionAlert,
  uiText,
  upsertPost,
}) {
  function findDiscussionActionItem(action) {
    return [
      ...discussionMenuItems.value,
      ...discussionSidebarActionItems.value,
      ...discussionMobileActionItems.value,
    ].find(entry => entry.key === action)
  }

  async function handleDiscussionMenuSelection(action) {
    const item = findDiscussionActionItem(action)
    if (!item || item.disabled) return

    const ran = await runDiscussionAction(item, {
      action: item.key,
      authStore,
      discussion: discussion.value || {},
      discussionActionHandlers,
      modalStore,
      patchDiscussion,
      setTogglingSubscription,
      showActionError,
    })
    if (ran) {
      showDiscussionMenu.value = false
    }
  }

  const discussionMenuItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    hasActiveComposer: hasActiveComposer.value,
    isSuspended: isSuspended.value,
    surface: 'discussion-menu',
    togglingSubscription: togglingSubscription.value
  }))

  const discussionSidebarActionItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    hasActiveComposer: hasActiveComposer.value,
    isSuspended: isSuspended.value,
    surface: 'discussion-sidebar',
    togglingSubscription: togglingSubscription.value
  }))

  const discussionMobileActionItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    hasActiveComposer: hasActiveComposer.value,
    isSuspended: isSuspended.value,
    surface: 'discussion-mobile-primary',
    togglingSubscription: togglingSubscription.value
  }))

  function hasPostControls(post) {
    return getPostMenuOptions(post).length > 0
  }

  function getPostMenuOptions(post) {
    return getPostMenuItems({
      canDeletePost,
      canEditPost,
      canModeratePostVisibility,
      canReportPost,
      post
    })
  }

  async function handlePostMenuSelection(post, action, extraContext = {}) {
    const item = getPostMenuOptions(post).find(entry => entry.key === action) || { key: action, action }
    if (!item || item.disabled) return
    const patchPost = (postId, patch) => {
      if (typeof upsertPost !== 'function') return null
      const targetPost = String(post?.id) === String(postId) ? post : { id: postId }
      return upsertPost({
        ...targetPost,
        ...(patch || {}),
        id: postId,
      })
    }

    const ran = await runPostAction(item, {
      action: item.key,
      authStore,
      discussion: discussion.value || {},
      isSuspended: isSuspended.value,
      modalStore,
      patchPost,
      post,
      postActionHandlers,
      showActionError,
      showSuspensionAlert,
      uiText,
      upsertPost,
      ...extraContext,
    })
    if (ran) {
      activePostMenuId.value = null
    }
  }

  return {
    discussionMenuItems,
    discussionMobileActionItems,
    discussionSidebarActionItems,
    getPostMenuOptions,
    handleDiscussionMenuSelection,
    handlePostMenuSelection,
    hasPostControls,
  }
}
