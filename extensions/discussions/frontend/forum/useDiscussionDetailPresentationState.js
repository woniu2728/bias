import { useDiscussionDetailPermissionState } from './useDiscussionDetailPermissionState'
import { getPostTypeDefinition } from '@bias/posts'
import { getUiCopy } from '@bias/forum'
import { useDiscussionDetailInteractions } from './useDiscussionDetailInteractions'
import { useDiscussionDetailMenus } from './useDiscussionDetailMenus'
import { useDiscussionDetailPresentation } from './useDiscussionDetailPresentation'
import DiscussionPostItem from './components/DiscussionPostItem.vue'

export function useDiscussionDetailPresentationState({
  activePostMenuId,
  authStore,
  closePostMenu,
  composerStore,
  discussion,
  discussionMobileNavRef,
  forumStore,
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
    forumStore,
    hasActiveComposer,
    isDiscussionActionPending: interactions.isDiscussionActionPending,
    isSuspended: permissionState.isSuspended,
    modalStore,
    pendingDiscussionActions: interactions.pendingDiscussionActions,
    patchDiscussion,
    router,
    setDiscussionActionPending: interactions.setDiscussionActionPending,
    showDiscussionMenu: pageState.showDiscussionMenu,
    discussionActionHandlers: interactions.discussionActionHandlers,
    postActionHandlers: interactions.postActionHandlers,
    showActionError: interactions.showActionError,
    showSuspensionAlert: interactions.showSuspensionAlert,
    uiText: interactions.uiText,
    upsertPost,
  })

  function resolvePostComponent(post) {
    return getPostTypeDefinition(post?.type)?.component || DiscussionPostItem
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
