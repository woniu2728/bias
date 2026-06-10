import { formatRelativeTime } from '@bias/core'
import { useDiscussionListMetaState } from './useDiscussionListMetaState'
import { useDiscussionListPage } from './useDiscussionListPage'
import { useDiscussionListViewBindings } from './useDiscussionListViewBindings'
import { buildDiscussionPath } from '@bias/discussions'
import {
  buildUserPath,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
} from '@bias/users'

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
    forumStore,
    modalStore,
    route,
    router
  })
  const metaState = useDiscussionListMetaState({
    contextSubject: pageState.contextSubject,
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
    buildUserPath,
    changeSortBy: pageState.changeSortBy,
    contextSubject: pageState.contextSubject,
    discussionListContexts: pageState.discussionListContexts,
    discussions: pageState.discussions,
    emptyStateText: pageState.emptyStateText,
    formatRelativeTime,
    getUserAvatarColor,
    getUserDisplayName,
    getUserInitial,
    handleStartDiscussion: pageState.handleStartDiscussion,
    hasMore: pageState.hasMore,
    isFollowingPage: pageState.isFollowingPage,
    isOwnProfilePage: pageState.isOwnProfilePage,
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
    sidebarExtensionSections: pageState.sidebarExtensionSections,
    sidebarFilterItems: pageState.sidebarFilterItems,
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
