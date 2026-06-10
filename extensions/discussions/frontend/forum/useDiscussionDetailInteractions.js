import { useDiscussionDetailModerationActions } from './useDiscussionDetailModerationActions'
import { createDiscussionActionHandlers, createPostActionHandlers } from './discussionDetailActionHandlers'
import { useDiscussionDetailUserActions } from './useDiscussionDetailUserActions'

export function useDiscussionDetailInteractions({
  authStore,
  canEditDiscussion,
  canModeratePostVisibility,
  composerStore,
  discussion,
  formatAbsoluteDate,
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
  upsertPost
}) {
  const userActions = useDiscussionDetailUserActions({
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
  })

  const moderationActions = useDiscussionDetailModerationActions({
    canModeratePostVisibility,
    discussion,
    modalStore,
    patchDiscussion,
    refreshDiscussion,
    router,
    showActionError: userActions.showActionError,
    uiText: userActions.uiText,
  })
  const discussionActionHandlers = createDiscussionActionHandlers({
    deleteDiscussion: moderationActions.deleteDiscussion,
    editDiscussion: userActions.editDiscussion,
    goToLoginForReply: userActions.goToLoginForReply,
    openComposer: userActions.openComposer,
    shareDiscussion: userActions.shareDiscussion,
    toggleHide: moderationActions.toggleHide,
    toggleLock: moderationActions.toggleLock,
    togglePin: moderationActions.togglePin,
  })
  const postActionHandlers = createPostActionHandlers({
    deletePost: userActions.deletePost,
    editPost: userActions.editPost,
    togglePostHidden: moderationActions.togglePostHidden,
  })

  return {
    formatAbsoluteDate,
    formatDate: userActions.formatDate,
    goToLoginForReply: userActions.goToLoginForReply,
    isSuspended,
    openComposer: userActions.openComposer,
    postActionHandlers,
    replyToPost: userActions.replyToPost,
    shareDiscussion: userActions.shareDiscussion,
    discussionActionHandlers,
    showSuspensionAlert: userActions.showSuspensionAlert,
    suspensionNotice,
    ...moderationActions,
    ...userActions,
  }
}
