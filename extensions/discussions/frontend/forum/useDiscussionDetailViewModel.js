import {
  useDiscussionDetailMetaState } from './useDiscussionDetailMetaState'
import { useDiscussionDetailPage } from './useDiscussionDetailPage'
import { useDiscussionDetailPresentationState } from './useDiscussionDetailPresentationState'
import { useDiscussionDetailViewBindings } from './useDiscussionDetailViewBindings'
import { buildUserPath, getUserAvatarColor, getUserDisplayName, getUserInitial } from '@bias/users'

export function useDiscussionDetailViewModel({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  route,
  router,
}) {
  const pageState = useDiscussionDetailPage({
    authStore,
    composerStore,
    forumStore,
    route,
    router,
  })

  const {
    activePostMenuId,
    closePostMenu,
    discussion,
    discussionMobileNavRef,
    hasActiveComposer,
    patchDiscussion,
    refreshDiscussion,
    removePost,
    scrollToPost,
    totalPosts,
    upsertPost,
    ...pageBindings
  } = pageState
  const presentationState = useDiscussionDetailPresentationState({
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
  })
  const metaState = useDiscussionDetailMetaState({
    discussion,
    forumStore,
    loading: pageState.loading,
  })
  const viewBindings = useDiscussionDetailViewBindings({
    ...pageBindings,
    ...metaState,
    ...presentationState,
    authStore,
    buildUserPath,
    forumStore,
    getUserAvatarColor,
    getUserDisplayName,
    getUserInitial,
  })

  return {
    ...pageBindings,
    ...metaState,
    ...presentationState,
    ...viewBindings,
  }
}
