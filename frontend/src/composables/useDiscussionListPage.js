import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { useDiscussionListPageActions } from '@/composables/useDiscussionListPageActions'
import { useDiscussionListPageState } from '@/composables/useDiscussionListPageState'

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
