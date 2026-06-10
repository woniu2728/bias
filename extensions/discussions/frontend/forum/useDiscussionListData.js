
import {
  api,
  ref,
  computed,
  useResourceStore } from '@bias/core'
import { getDiscussionListContexts } from '@bias/discussions'
import {
  useDiscussionListLoadState } from './useDiscussionListLoadState'
import { useDiscussionListPageLifecycle } from './useDiscussionListPageLifecycle'
import { useDiscussionListRealtimeLifecycleState } from './useDiscussionListRealtimeLifecycleState'
import { useDiscussionListRouteActions } from './useDiscussionListRouteActions'
import { useDiscussionListResourceState } from './useDiscussionListResourceState'
import { useDiscussionListRouteState } from './useDiscussionListRouteState'
import { useDiscussionListRealtimeState } from './useDiscussionListRealtimeState'
import { useForumRealtimeStore } from '@bias/realtime'

const DISCUSSION_LIST_RETURN_RESTORE_KEY = 'bias.discussionListReturnRestore'

export function useDiscussionListData({
  authStore,
  modalStore,
  route,
  router,
}) {
  const resourceStore = useResourceStore()
  const forumRealtimeStore = useForumRealtimeStore()
  const routeState = useDiscussionListRouteState({ route, router })
  const markingAllRead = ref(false)

  const searchQuery = routeState.searchQuery
  const sortBy = routeState.sortBy
  const listFilter = routeState.listFilter
  const isFollowingPage = computed(() => route.name === 'following' || listFilter.value === 'following')
  const discussionListContexts = computed(() => getDiscussionListContexts({
    authStore,
    isFollowingPage: isFollowingPage.value,
    listFilter: listFilter.value,
    route,
    searchQuery: searchQuery.value,
    sortBy: sortBy.value,
    surface: 'discussion-list',
  }))
  const primaryDiscussionListContext = computed(() => discussionListContexts.value[0] || null)
  const resourceState = useDiscussionListResourceState({
    discussionListContexts,
    isFollowingPage,
    listFilter,
    primaryDiscussionListContext,
    route,
    searchQuery,
    sortBy,
  })
  const loadState = useDiscussionListLoadState({
    modalStore,
    resourceState,
    route,
    searchQuery,
    sortBy,
    listFilter,
  })

  const realtimeState = useDiscussionListRealtimeState({
    api,
    authStore,
    currentDiscussionIds: resourceState.discussionIds,
    markingAllRead,
    modalStore,
    refreshDiscussionList: loadState.refreshDiscussionList,
    resourceStore,
    uiText: loadState.uiText,
  })
  const realtimeLifecycleState = useDiscussionListRealtimeLifecycleState({
    discussionIds: resourceState.discussionIds,
    forumEventHandler: realtimeState.handleForumEvent,
    forumRealtimeStore,
    readStateHandler: realtimeState.handleDiscussionReadStateUpdated,
  })

  useDiscussionListPageLifecycle({
    addDiscussionReadStateListener: realtimeLifecycleState.addDiscussionReadStateListener,
    addForumEventListener: realtimeLifecycleState.addForumEventListener,
    clearPendingReturnRestore,
    cleanupTrackedDiscussionIds: realtimeLifecycleState.cleanupTrackedDiscussionIds,
    currentDiscussionIds: resourceState.discussionIds,
    discussions: resourceState.discussions,
    getPendingReturnRestore,
    removeDiscussionReadStateListener: realtimeLifecycleState.removeDiscussionReadStateListener,
    removeForumEventListener: realtimeLifecycleState.removeForumEventListener,
    syncTrackedDiscussionIds: realtimeLifecycleState.syncTrackedDiscussionIds,
  })

  const routeActions = useDiscussionListRouteActions({
    routeState,
    listFilter,
    searchQuery,
    sortBy,
  })

  function buildReturnRestoreKey() {
    return JSON.stringify({
      name: route.name || null,
      params: route.params || {},
      query: {
        filter: routeState.listFilter.value || null,
        q: routeState.searchQuery.value || null,
        sort: routeState.sortBy.value || null,
      },
    })
  }

  function getPendingReturnRestore() {
    if (typeof window === 'undefined') return null

    const raw = window.sessionStorage.getItem(DISCUSSION_LIST_RETURN_RESTORE_KEY)
    if (!raw) return null

    let payload = null
    try {
      payload = JSON.parse(raw)
    } catch {
      window.sessionStorage.removeItem(DISCUSSION_LIST_RETURN_RESTORE_KEY)
      return null
    }

    if (!payload || payload.listKey !== buildReturnRestoreKey()) {
      return null
    }

    const discussionId = Number(payload.discussionId || 0)
    return Number.isFinite(discussionId) && discussionId > 0 ? discussionId : null
  }

  function clearPendingReturnRestore() {
    if (typeof window === 'undefined') return
    window.sessionStorage.removeItem(DISCUSSION_LIST_RETURN_RESTORE_KEY)
  }

  return {
    changeSortBy: routeActions.changeSortBy,
    clearPendingReturnRestore,
    contextSubject: resourceState.contextSubject,
    contextSubjectKey: resourceState.contextSubjectKey,
    discussionListContextData: resourceState.discussionListContextData,
    discussionListContexts,
    discussions: resourceState.discussions,
    filterOptions: resourceState.filterOptions,
    getPendingReturnRestore,
    hasMore: resourceState.hasMore,
    isFollowingPage,
    listFilter,
    loadMore: loadState.loadMore,
    loading: loadState.listState.loading,
    loadingMore: loadState.listState.loadingMore,
    markAllAsRead: realtimeState.markAllAsRead,
    changeListFilter: routeActions.changeListFilter,
    changeSearchQuery: routeActions.changeSearchQuery,
    markingAllRead,
    refreshPageData: loadState.refreshPageData,
    refreshDiscussionList: loadState.refreshDiscussionList,
    refreshing: loadState.listState.refreshing,
    searchQuery,
    sortBy,
    sortOptions: resourceState.sortOptions,
  }
}
