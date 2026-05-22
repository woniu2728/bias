import { useDiscussionListMetaState } from '@/composables/useDiscussionListMetaState'
import { useDiscussionListPage } from '@/composables/useDiscussionListPage'
import { useDiscussionListViewBindings } from '@/composables/useDiscussionListViewBindings'
import {
  buildDiscussionPath,
  buildTagPath,
  buildUserPath,
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
} from '@/utils/forum'

export function useDiscussionListViewModel({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  pageState: injectedPageState,
  route,
  router,
}) {
  const pageState = injectedPageState || useDiscussionListPage({
    authStore,
    composerStore,
    modalStore,
    route,
    router
  })
  const metaState = useDiscussionListMetaState({
    currentTag: pageState.currentTag,
    forumStore,
    isFollowingPage: pageState.isFollowingPage,
    listFilter: pageState.listFilter,
    route,
    searchQuery: pageState.searchQuery,
  })
  const viewBindings = useDiscussionListViewBindings({
    authStore,
    buildDiscussionPath,
    buildTrackedDiscussionPath(value) {
      const discussion = value && typeof value === 'object' ? value : { id: value }
      const path = buildDiscussionPath(discussion)

      if (!discussion?.id) {
        return path
      }

      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem('bias.discussionListReturnRestore', JSON.stringify({
          discussionId: discussion.id,
          listKey: JSON.stringify({
            name: route.name || null,
            params: route.params || {},
            query: {
              filter: pageState.listFilter.value || null,
              q: pageState.searchQuery.value || null,
              sort: pageState.sortBy.value || null,
            },
          }),
        }))
      }

      return {
        path,
        query: {
          returnTo: route.fullPath,
          returnDiscussion: discussion.id,
        },
      }
    },
    buildTagPath,
    buildUserPath,
    changeSortBy: pageState.changeSortBy,
    currentTag: pageState.currentTag,
    discussions: pageState.discussions,
    emptyStateText: pageState.emptyStateText,
    formatRelativeTime,
    getSidebarTagStyle: pageState.getSidebarTagStyle,
    getUserAvatarColor,
    getUserDisplayName,
    getUserInitial,
    handleStartDiscussion: pageState.handleStartDiscussion,
    hasMore: pageState.hasMore,
    hasSidebarTagNavigation: pageState.hasSidebarTagNavigation,
    isFollowingPage: pageState.isFollowingPage,
    isOwnProfilePage: pageState.isOwnProfilePage,
    isSidebarTagActive: pageState.isSidebarTagActive,
    isTagsPage: pageState.isTagsPage,
    listFilter: pageState.listFilter,
    loading: pageState.loading,
    loadingMore: pageState.loadingMore,
    loadingStateText: pageState.loadingStateText,
    loadMore: pageState.loadMore,
    markingAllRead: pageState.markingAllRead,
    markAllAsRead: pageState.markAllAsRead,
    refreshDiscussionList: pageState.refreshDiscussionList,
    refreshing: pageState.refreshing,
    showMoreTagsLink: pageState.showMoreTagsLink,
    sidebarFilterItems: pageState.sidebarFilterItems,
    sidebarPrimaryTagItems: pageState.sidebarPrimaryTagItems,
    sidebarSecondaryTagItems: pageState.sidebarSecondaryTagItems,
    sortBy: pageState.sortBy,
    sortOptions: pageState.sortOptions,
    startDiscussionButtonStyle: pageState.startDiscussionButtonStyle,
  })

  return {
    ...pageState,
    ...metaState,
    ...viewBindings,
  }
}
