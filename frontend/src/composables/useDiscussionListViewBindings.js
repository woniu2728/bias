import { computed } from 'vue'

export function createDiscussionListViewBindings({
  authStore,
  buildDiscussionPath,
  buildTrackedDiscussionPath,
  buildTagPath,
  buildUserPath,
  changeSortBy,
  currentTag,
  discussions,
  emptyStateText,
  formatRelativeTime,
  getSidebarTagStyle,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  handleStartDiscussion,
  hasMore,
  hasSidebarTagNavigation,
  isFollowingPage,
  isOwnProfilePage,
  isSidebarTagActive,
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
  showMoreTagsLink,
  sidebarFilterItems,
  sidebarPrimaryTagItems,
  sidebarSecondaryTagItems,
  sortBy,
  sortOptions,
  startDiscussionButtonStyle,
}) {
  const sidebarBindings = computed(() => ({
    authStore,
    currentTag: currentTag.value,
    isOwnProfilePage: isOwnProfilePage.value,
    sidebarFilterItems: sidebarFilterItems.value,
    isTagsPage: isTagsPage.value,
    hasSidebarTagNavigation: hasSidebarTagNavigation.value,
    sidebarPrimaryTagItems: sidebarPrimaryTagItems.value,
    sidebarSecondaryTagItems: sidebarSecondaryTagItems.value,
    showMoreTagsLink: showMoreTagsLink.value,
    startDiscussionButtonStyle: startDiscussionButtonStyle.value,
    buildUserPath,
    buildTagPath,
    isSidebarTagActive,
    getSidebarTagStyle,
  }))

  const sidebarEvents = {
    startDiscussion: handleStartDiscussion,
  }

  const contentBindings = computed(() => ({
    authStore,
    currentTag: currentTag.value,
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
    buildTagPath,
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
