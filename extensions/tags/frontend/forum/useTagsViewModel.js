import { useStartDiscussionAction } from '@bias/forum'
import { computed } from '@bias/forum'
import { useTagsMetaState } from './useTagsMetaState.js'
import { useTagsPage } from './useTagsPage.js'
import { useTagsViewBindings } from './useTagsViewBindings.js'

export function useTagsViewModel({
  authStore,
  composerStore,
  forumStore,
  pageState: injectedPageState,
  router,
}) {
  const pageState = injectedPageState || useTagsPage()
  const { startDiscussion } = useStartDiscussionAction({
    authStore,
    composerStore,
    router,
  })
  const metaState = useTagsMetaState({
    forumStore,
    loading: pageState.loading,
    tags: pageState.tags,
  })

  const showStartDiscussionButton = computed(() => {
    return !authStore.isAuthenticated || authStore.canStartDiscussion
  })

  function handleStartDiscussion() {
    startDiscussion({
      source: 'tags',
    })
  }

  const viewBindings = useTagsViewBindings({
    authStore,
    cloudTags: pageState.cloudTags,
    emptyStateText: metaState.emptyStateText,
    handleStartDiscussion,
    heroDescriptionText: metaState.heroDescriptionText,
    heroTitleText: metaState.heroTitleText,
    loading: pageState.loading,
    loadingStateText: metaState.loadingStateText,
    showStartDiscussionButton,
    tags: pageState.tags,
  })

  return {
    ...pageState,
    ...metaState,
    ...viewBindings,
    handleStartDiscussion,
    showStartDiscussionButton,
  }
}
