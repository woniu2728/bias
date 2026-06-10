import { useStartDiscussionAction } from '@bias/discussions'
import { useDiscussionListPageActions } from './useDiscussionListPageActions'
import { useDiscussionListPageState } from './useDiscussionListPageState'

export function useDiscussionListPage({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  route,
  router
}) {
  const { startDiscussion } = useStartDiscussionAction({
    authStore,
    composerStore,
    router
  })
  const pageState = useDiscussionListPageState({
    authStore,
    forumStore,
    modalStore,
    route,
    router,
  })
  const pageActions = useDiscussionListPageActions({
    discussionListContextData: pageState.discussionListContextData,
    route,
    startDiscussion,
  })

  return {
    ...pageState,
    handleStartDiscussion: pageActions.handleStartDiscussion,
  }
}
