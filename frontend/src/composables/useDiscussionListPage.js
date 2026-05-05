import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { useDiscussionListData } from '@/composables/useDiscussionListData'
import { useDiscussionListNavigation } from '@/composables/useDiscussionListNavigation'

export function useDiscussionListPage({
  authStore,
  composerStore,
  modalStore,
  route,
  router
}) {
  const { startDiscussion } = useStartDiscussionAction({
    authStore,
    composerStore,
    router
  })
  const {
    discussions,
    currentTag,
    currentTagSlug,
    loading,
    refreshing,
    loadingMore,
    sortBy,
    markingAllRead,
    hasMore,
    isFollowingPage,
    tags,
    sortOptions,
    filterOptions,
    listFilter,
    searchQuery,
    refreshPageData,
    refreshDiscussionList,
    changeSortBy,
    changeListFilter,
    changeSearchQuery,
    loadMore,
    markAllAsRead
  } = useDiscussionListData({
    authStore,
    modalStore,
    route,
    router,
  })
  const {
    isTagsPage,
    isAllDiscussionsPage,
    isOwnProfilePage,
    sidebarPrimaryTagItems,
    sidebarSecondaryTagItems,
    hasSidebarTagNavigation,
    showMoreTagsLink,
    startDiscussionButtonStyle,
    emptyStateText,
    getSidebarTagStyle,
    isSidebarTagActive
  } = useDiscussionListNavigation({
    authStore,
    currentTag,
    currentTagSlug,
    isFollowingPage,
    listFilter,
    route,
    tags
  })

  function handleStartDiscussion() {
    startDiscussion({
      tagId: currentTag.value?.id,
      source: route.name?.toString() || 'index'
    })
  }

  return {
    discussions,
    currentTag,
    loading,
    refreshing,
    loadingMore,
    sortBy,
    sortOptions,
    filterOptions,
    listFilter,
    searchQuery,
    markingAllRead,
    hasMore,
    isFollowingPage,
    isTagsPage,
    isAllDiscussionsPage,
    isOwnProfilePage,
    sidebarPrimaryTagItems,
    sidebarSecondaryTagItems,
    hasSidebarTagNavigation,
    showMoreTagsLink,
    startDiscussionButtonStyle,
    emptyStateText,
    refreshPageData,
    refreshDiscussionList,
    changeSortBy,
    changeListFilter,
    changeSearchQuery,
    loadMore,
    markAllAsRead,
    handleStartDiscussion,
    getSidebarTagStyle,
    isSidebarTagActive
  }
}
