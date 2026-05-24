import { useDiscussionListData } from '@/composables/useDiscussionListData'
import { useDiscussionListNavigation } from '@/composables/useDiscussionListNavigation'

export function useDiscussionListPageState({
  authStore,
  forumStore,
  modalStore,
  route,
  router,
}) {
  const dataState = useDiscussionListData({
    authStore,
    modalStore,
    route,
    router,
  })

  const navigationState = useDiscussionListNavigation({
    authStore,
    currentTag: dataState.currentTag,
    currentTagSlug: dataState.currentTagSlug,
    filterOptions: dataState.filterOptions,
    forumStore,
    isFollowingPage: dataState.isFollowingPage,
    listFilter: dataState.listFilter,
    route,
    tags: dataState.tags,
  })

  return {
    ...dataState,
    ...navigationState,
  }
}
