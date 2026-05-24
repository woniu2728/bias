import { computed } from 'vue'
import { useRoutePagination } from '@/composables/useRoutePagination'
import { useSearchFilterCatalog } from '@/composables/useSearchFilterCatalog'
import { useSearchResultsLoadState } from '@/composables/useSearchResultsLoadState'
import { useSearchResultsPageLifecycle } from '@/composables/useSearchResultsPageLifecycle'
import { useSearchResultsRealtimeState } from '@/composables/useSearchResultsRealtimeState'
import { useSearchResultsResourceState } from '@/composables/useSearchResultsResourceState'
import { useSearchResultsRouteActions } from '@/composables/useSearchResultsRouteActions'
import { useSearchRouteState } from '@/composables/useSearchRouteState'
import { getEmptyState, getSearchSources, getStateBlock, getUiCopy } from '@/forum/registry'
import { useForumStore } from '@/stores/forum'
import { useForumRealtimeStore } from '@/stores/forumRealtime'
import { useResourceStore } from '@/stores/resource'

export function useSearchResultsPage({ route, router }) {
  const forumStore = useForumStore()
  const routeState = useSearchRouteState({ forumStore, route, router })
  const resourceStore = useResourceStore()
  const forumRealtimeStore = useForumRealtimeStore()
  const searchSources = getSearchSources({ forumStore })
  const sourceMap = Object.fromEntries(searchSources.map(item => [item.routeType || item.type, item]))
  const resourceState = useSearchResultsResourceState({
    resourceStore,
    searchSources,
  })
  const normalizedQuery = routeState.normalizedQuery
  const searchType = routeState.searchType
  const activeSource = computed(() => sourceMap[searchType.value] || null)
  const searchFilterTarget = computed(() => {
    return activeSource.value?.filterTarget || (searchType.value === 'all' ? 'discussion' : '')
  })
  const searchFilterCatalog = useSearchFilterCatalog(searchFilterTarget)
  const page = routeState.page
  const routePagination = useRoutePagination({
    page,
    push: routeState.push,
  })
  const loadState = useSearchResultsLoadState({
    activeSource,
    normalizedQuery,
    page,
    resourceState,
    searchFilterCatalog,
    searchType,
  })
  const emptyStateText = computed(() => {
    const emptyState = getEmptyState({
      surface: 'search-page-empty',
      hasQuery: Boolean(normalizedQuery.value),
      searchType: searchType.value,
    })

    return emptyState?.text || '没有找到相关讨论、帖子或用户。'
  })
  const idleStateText = computed(() => {
    const emptyState = getEmptyState({
      surface: 'search-page-idle',
      hasQuery: Boolean(normalizedQuery.value),
      searchType: searchType.value,
    })

    return emptyState?.text || '请输入关键词后再搜索。'
  })
  const loadingStateText = computed(() => {
    const stateBlock = getStateBlock({
      surface: 'search-page-loading',
      loading: loading.value,
      hasQuery: Boolean(normalizedQuery.value),
      searchType: searchType.value,
    })

    return stateBlock?.text || '搜索中...'
  })
  const loading = loadState.listState.loading

  function getSearchUiCopy(surface, context = {}, fallback = '') {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  const filterItems = computed(() => {
    const counts = {
      discussions: resourceState.discussionTotal.value,
      posts: resourceState.postTotal.value,
      users: resourceState.userTotal.value,
    }

    return [
      {
        value: 'all',
        label: getUiCopy({
          surface: 'search-filter-all-label',
          count: resourceState.discussionTotal.value + resourceState.postTotal.value + resourceState.userTotal.value,
        })?.text || '全部',
        count: getSearchUiCopy(
          'search-results-total-count',
          { count: resourceState.discussionTotal.value + resourceState.postTotal.value + resourceState.userTotal.value },
          String(resourceState.discussionTotal.value + resourceState.postTotal.value + resourceState.userTotal.value)
        )
      },
      ...searchSources.map(item => ({
        value: item.routeType || item.type,
        label: item.label,
        count: getSearchUiCopy(
          'search-results-source-count',
          {
            count: Number(counts[item.routeType || item.type] || 0),
            type: item.routeType || item.type,
          },
          String(Number(counts[item.routeType || item.type] || 0))
        ),
      })),
    ]
  })
  const heroText = computed(() => {
    const uiCopy = getUiCopy({
      surface: 'search-page-hero-description',
      hasQuery: Boolean(normalizedQuery.value),
      searchType: searchType.value,
      total: resourceState.total.value,
      discussionTotal: resourceState.discussionTotal.value,
      postTotal: resourceState.postTotal.value,
      userTotal: resourceState.userTotal.value,
      activeLabel: activeSource.value?.label || '结果',
    })
    if (uiCopy?.text) {
      return uiCopy.text
    }

    if (!normalizedQuery.value) {
      return '支持在讨论、帖子和用户之间进行全局搜索。'
    }

    if (searchType.value === 'all') {
      return `共找到 ${resourceState.discussionTotal.value + resourceState.postTotal.value + resourceState.userTotal.value} 条结果，已按讨论、帖子和用户分组展示。`
    }

    const label = activeSource.value?.label || '结果'
    return `当前显示 ${label}结果，共 ${resourceState.total.value} 条。`
  })
  const syntaxItems = computed(() => {
    if (!searchFilterTarget.value) {
      return []
    }
    return searchFilterCatalog.filterSuggestions.value
  })
  const searchSourceSections = computed(() => resourceState.buildSearchSourceSections({
    normalizedQuery: normalizedQuery.value,
    searchType: searchType.value,
  }))

  function addForumEventListener() {
    if (typeof window === 'undefined') return
    window.addEventListener('bias:forum-event', realtimeState.handleForumEvent)
  }

  function removeForumEventListener() {
    if (typeof window === 'undefined') return
    window.removeEventListener('bias:forum-event', realtimeState.handleForumEvent)
  }

  function cleanupTrackedDiscussionIds() {
    forumRealtimeStore.untrackDiscussionIds(resourceState.trackedDiscussionIds.value)
  }

  function syncTrackedDiscussionIds(nextTrackedIds, previousTrackedIds = []) {
    forumRealtimeStore.untrackDiscussionIds(previousTrackedIds)
    forumRealtimeStore.trackDiscussionIds(nextTrackedIds)
  }

  const realtimeState = useSearchResultsRealtimeState({
    loadResults: loadState.refreshResults,
    resourceStore,
    trackedDiscussionIds: resourceState.trackedDiscussionIds,
  })
  const routeActions = useSearchResultsRouteActions({
    appendFilter: searchFilterCatalog.appendFilter,
    normalizedQuery,
    routePagination,
    searchSources,
    searchType,
  })

  useSearchResultsPageLifecycle({
    abortActiveRequest: loadState.abortActiveRequest,
    addForumEventListener,
    cleanupTrackedDiscussionIds,
    forumEventHandler: realtimeState.handleForumEvent,
    removeForumEventListener,
    syncTrackedDiscussionIds,
    trackedDiscussionIds: resourceState.trackedDiscussionIds,
  })

  return {
    changePage: routeActions.changePage,
    changeType: routeActions.changeType,
    discussionTotal: resourceState.discussionTotal,
    discussions: resourceState.discussions,
    emptyStateText,
    filterItems,
    filterCatalogLoadError: searchFilterCatalog.loadError,
    applySyntax: routeActions.applySyntax,
    heroText,
    idleStateText,
    loadingStateText,
    isEmpty: resourceState.isEmpty,
    loading,
    normalizedQuery,
    page,
    postTotal: resourceState.postTotal,
    posts: resourceState.posts,
    searchType,
    showDiscussions: computed(() => searchType.value === 'all' || searchType.value === 'discussions'),
    showPosts: computed(() => searchType.value === 'all' || searchType.value === 'posts'),
    showUsers: computed(() => searchType.value === 'all' || searchType.value === 'users'),
    searchSourceSections,
    syntaxItems,
    total: resourceState.total,
    totalPages: resourceState.totalPages,
    userTotal: resourceState.userTotal,
    users: resourceState.users
  }
}
