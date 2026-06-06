import { useDiscussionDetailMetaState } from '@/composables/useDiscussionDetailMetaState'
import { useDiscussionDetailPage } from '@/composables/useDiscussionDetailPage'
import { useDiscussionDetailPresentationState } from '@/composables/useDiscussionDetailPresentationState'
import { useDiscussionDetailViewBindings } from '@/composables/useDiscussionDetailViewBindings'
import {
  buildUserPath,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
} from '@/utils/forum'

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
