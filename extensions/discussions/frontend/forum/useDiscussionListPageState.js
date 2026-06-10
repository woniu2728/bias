import { useDiscussionListData } from './useDiscussionListData'
import { useDiscussionListNavigation } from './useDiscussionListNavigation'

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
    contextSubject: dataState.contextSubject,
    contextSubjectKey: dataState.contextSubjectKey,
    discussionListContextData: dataState.discussionListContextData,
    discussionListContexts: dataState.discussionListContexts,
    filterOptions: dataState.filterOptions,
    forumStore,
    isFollowingPage: dataState.isFollowingPage,
    listFilter: dataState.listFilter,
    route,
  })

  return {
    ...dataState,
    ...navigationState,
  }
}
