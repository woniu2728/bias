import { computed } from '@bias/forum'

export function createTagsViewBindings({
  authStore,
  cloudTags,
  emptyStateText,
  handleStartDiscussion,
  heroDescriptionText,
  heroTitleText,
  loading,
  loadingStateText,
  showStartDiscussionButton,
  tags,
}) {
  const sidebarBindings = computed(() => ({
    authStore,
    showStartDiscussionButton: showStartDiscussionButton.value,
  }))

  const sidebarEvents = {
    startDiscussion: handleStartDiscussion,
  }

  const heroBindings = computed(() => ({
    title: heroTitleText.value,
    description: heroDescriptionText.value,
    variant: 'default',
  }))

  const contentBindings = computed(() => ({
    cloudTags: cloudTags.value,
    emptyStateText: emptyStateText.value,
    loading: loading.value,
    loadingStateText: loadingStateText.value,
    tags: tags.value,
  }))

  return {
    contentBindings,
    heroBindings,
    sidebarBindings,
    sidebarEvents,
  }
}

export function useTagsViewBindings(options) {
  return createTagsViewBindings(options)
}
