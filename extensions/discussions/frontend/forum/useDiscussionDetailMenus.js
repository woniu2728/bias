
import { computed } from '@bias/core'
import { runDiscussionAction, getDiscussionMenuItems } from '@bias/discussions'
import { runPostAction, getPostMenuItems } from '@bias/posts'

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
  forumStore,
  hasActiveComposer,
  isDiscussionActionPending = () => false,
  isSuspended,
  pendingDiscussionActions = { value: {} },
  showDiscussionMenu,
  discussionActionHandlers,
  postActionHandlers,
  modalStore,
  patchDiscussion,
  router,
  setDiscussionActionPending = () => {},
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
      forumStore,
      isDiscussionActionPending,
      modalStore,
      pendingDiscussionActions: pendingDiscussionActions.value,
      patchDiscussion,
      setActionPending: setDiscussionActionPending,
      setDiscussionActionPending,
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
    forumStore,
    hasActiveComposer: hasActiveComposer.value,
    isDiscussionActionPending,
    isSuspended: isSuspended.value,
    pendingDiscussionActions: pendingDiscussionActions.value,
    surface: 'discussion-menu',
  }))

  const discussionSidebarActionItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    forumStore,
    hasActiveComposer: hasActiveComposer.value,
    isDiscussionActionPending,
    isSuspended: isSuspended.value,
    pendingDiscussionActions: pendingDiscussionActions.value,
    surface: 'discussion-sidebar',
  }))

  const discussionMobileActionItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    forumStore,
    hasActiveComposer: hasActiveComposer.value,
    isDiscussionActionPending,
    isSuspended: isSuspended.value,
    pendingDiscussionActions: pendingDiscussionActions.value,
    surface: 'discussion-mobile-primary',
  }))

  function hasPostControls(post) {
    return getPostMenuOptions(post).length > 0
  }

  function getPostActionOptions(post, surface) {
    return getPostMenuItems({
      authStore,
      canDeletePost,
      canEditPost,
      canModeratePostVisibility,
      canReportPost,
      discussion: discussion.value || {},
      forumStore,
      isSuspended: isSuspended.value,
      post,
      surface,
      uiText,
    })
  }

  function getPostMenuOptions(post) {
    return getPostActionOptions(post, 'post-menu')
  }

  function getPostPrimaryActions(post) {
    return getPostActionOptions(post, 'discussion-post-primary')
  }

  function getPostFeedbackActions(post) {
    return getPostActionOptions(post, 'discussion-post-feedback')
  }

  function createPostActionContext(post, item, extraContext = {}) {
    const patchPost = (postId, patch) => {
      if (typeof upsertPost !== 'function') return null
      const targetPost = String(post?.id) === String(postId) ? post : { id: postId }
      return upsertPost({
        ...targetPost,
        ...(patch || {}),
        id: postId,
      })
    }

    return {
      action: item.action || item.key,
      authStore,
      discussion: discussion.value || {},
      forumStore,
      isSuspended: isSuspended.value,
      modalStore,
      patchPost,
      post,
      postActionHandlers,
      router,
      showActionError,
      showSuspensionAlert,
      uiText,
      upsertPost,
      ...extraContext,
    }
  }

  async function handlePostActionSelection(post, action, extraContext = {}) {
    const surface = extraContext.surface || 'post-menu'
    const item = getPostActionOptions(post, surface).find(entry => entry.key === action || entry.action === action) || { key: action, action }
    if (!item || item.disabled) return

    const ran = await runPostAction(item, createPostActionContext(post, item, extraContext))
    if (ran) {
      activePostMenuId.value = null
    }
  }

  return {
    discussionMenuItems,
    discussionMobileActionItems,
    discussionSidebarActionItems,
    getPostFeedbackActions,
    getPostMenuOptions,
    getPostPrimaryActions,
    handleDiscussionMenuSelection,
    handlePostActionSelection,
    handlePostMenuSelection: handlePostActionSelection,
    hasPostControls,
  }
}
