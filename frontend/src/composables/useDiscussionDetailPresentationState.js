import { useDiscussionDetailPermissionState } from '@/composables/useDiscussionDetailPermissionState'
import { getPostTypeDefinition } from '@/forum/postTypes'
import { getUiCopy } from '@/forum/registry'
import { useDiscussionDetailInteractions } from '@/composables/useDiscussionDetailInteractions'
import { useDiscussionDetailMenus } from '@/composables/useDiscussionDetailMenus'
import { useDiscussionDetailPresentation } from '@/composables/useDiscussionDetailPresentation'

export function useDiscussionDetailPresentationState({
  activePostMenuId,
  authStore,
  closePostMenu,
  composerStore,
  discussion,
  discussionMobileNavRef,
  hasActiveComposer,
  modalStore,
  pageState,
  patchDiscussion,
  refreshDiscussion,
  removePost,
  route,
  router,
  scrollToPost,
  totalPosts,
  upsertPost,
}) {
  const permissionState = useDiscussionDetailPermissionState({
    authStore,
    discussion,
    resolveUiText(surface, fallback, context = {}) {
      return getUiCopy({
        surface,
        ...context,
      })?.text || fallback
    },
  })

  const interactions = useDiscussionDetailInteractions({
    authStore,
    canEditDiscussion: permissionState.canEditDiscussion,
    canLikePost: permissionState.canLikePost,
    canModeratePendingDiscussion: permissionState.canModeratePendingDiscussion,
    canModeratePendingPost: permissionState.canModeratePendingPost,
    canModeratePostVisibility: permissionState.canModeratePostVisibility,
    composerStore,
    discussion,
    formatAbsoluteDate: permissionState.formatAbsoluteDate,
    hasActiveComposer,
    isSuspended: permissionState.isSuspended,
    modalStore,
    patchDiscussion,
    refreshDiscussion,
    removePost,
    route,
    router,
    suspensionNotice: permissionState.suspensionNotice,
    scrollToPost,
    totalPosts,
    upsertPost
  })

  const presentation = useDiscussionDetailPresentation(discussion)

  const menus = useDiscussionDetailMenus({
    activePostMenuId,
    authStore,
    canDeletePost: permissionState.canDeletePost,
    canEditPost: permissionState.canEditPost,
    canModeratePostVisibility: permissionState.canModeratePostVisibility,
    canReportPost: permissionState.canReportPost,
    canEditDiscussion: permissionState.canEditDiscussion,
    canModerateDiscussionSettings: permissionState.canModerateDiscussionSettings,
    canReplyFromMenu: permissionState.canReplyFromMenu,
    discussion,
    hasActiveComposer,
    isSuspended: permissionState.isSuspended,
    modalStore,
    patchDiscussion,
    setTogglingSubscription: interactions.setTogglingSubscription,
    showDiscussionMenu: pageState.showDiscussionMenu,
    discussionActionHandlers: interactions.discussionActionHandlers,
    postActionHandlers: interactions.postActionHandlers,
    showActionError: interactions.showActionError,
    showSuspensionAlert: interactions.showSuspensionAlert,
    togglingSubscription: interactions.togglingSubscription,
    uiText: interactions.uiText,
    upsertPost,
  })

  function resolvePostComponent(post) {
    return getPostTypeDefinition(post?.type)?.component
  }

  return {
    ...permissionState,
    ...interactions,
    ...menus,
    ...presentation,
    activePostMenuId,
    closePostMenu,
    discussion,
    discussionMobileNavRef,
    hasActiveComposer,
    resolvePostComponent,
  }
}
