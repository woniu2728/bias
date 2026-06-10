import { computed } from '@bias/core'

export function createDiscussionListViewBindings({
  authStore,
  buildDiscussionPath,
  buildTrackedDiscussionPath,
  buildUserPath,
  changeSortBy,
  contextSubject,
  discussionListContexts,
  discussions,
  emptyStateText,
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  handleStartDiscussion,
  hasMore,
  isFollowingPage,
  isOwnProfilePage,
  isTagsPage,
  listFilter,
  loading,
  loadingMore,
  loadingStateText,
  loadMore,
  markingAllRead,
  markAllAsRead,
  refreshDiscussionList,
  refreshing,
  sidebarExtensionSections,
  sidebarFilterItems,
  sortBy,
  sortOptions,
  startDiscussionButtonStyle,
}) {
  const sidebarBindings = computed(() => ({
    authStore,
    contextSubject: contextSubject.value,
    isOwnProfilePage: isOwnProfilePage.value,
    sidebarFilterItems: sidebarFilterItems.value,
    isTagsPage: isTagsPage.value,
    sidebarExtensionSections: sidebarExtensionSections?.value || [],
    startDiscussionButtonStyle: startDiscussionButtonStyle.value,
    buildUserPath,
  }))

  const sidebarEvents = {
    startDiscussion: handleStartDiscussion,
  }

  const contentBindings = computed(() => ({
    authStore,
    contextSubject: contextSubject.value,
    discussionListContexts: discussionListContexts?.value || [],
    isFollowingPage: isFollowingPage.value,
    listFilter: listFilter.value,
    sortBy: sortBy.value,
    sortOptions: sortOptions.value,
    markingAllRead: markingAllRead.value,
    loading: loading.value,
    refreshing: refreshing.value,
    discussions: discussions.value,
    emptyStateText: emptyStateText.value,
    loadingStateText: loadingStateText.value,
    hasMore: hasMore.value,
    loadingMore: loadingMore.value,
    buildDiscussionPath: buildTrackedDiscussionPath || buildDiscussionPath,
    buildUserPath,
    formatRelativeTime,
    getUserAvatarColor,
    getUserDisplayName,
    getUserInitial,
  }))

  const contentEvents = {
    changeSort: changeSortBy,
    markAllRead: markAllAsRead,
    refresh: refreshDiscussionList,
    loadMore,
  }

  return {
    contentBindings,
    contentEvents,
    sidebarBindings,
    sidebarEvents,
  }
}

export function useDiscussionListViewBindings(options) {
  return createDiscussionListViewBindings(options)
}
