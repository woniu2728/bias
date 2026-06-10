import { computed } from '@bias/core'

export function createSearchResultsViewBindings({
  applySyntax,
  authStore,
  changePage,
  changeType,
  emptyStateText,
  filterCatalogLoadError,
  filterItems,
  handleStartDiscussion,
  heroPillText,
  heroText,
  heroTitleText,
  idleStateText,
  isEmpty,
  loading,
  loadingStateText,
  normalizedQuery,
  openSearchResult,
  page,
  searchStatsItems,
  searchType,
  syntaxItems,
  totalPages,
  visibleSearchSections,
}) {
  const sidebarBindings = computed(() => ({
    authStore,
    showStartDiscussionButton: !authStore.isAuthenticated || authStore.canStartDiscussion,
    filterItems: filterItems.value,
    searchType: searchType.value,
  }))

  const sidebarEvents = {
    changeType,
    startDiscussion: handleStartDiscussion,
  }

  const heroBindings = computed(() => ({
    pill: heroPillText.value,
    title: heroTitleText.value,
    description: heroText.value,
    variant: 'primary',
    normalizedQuery: normalizedQuery.value,
    searchStatsItems: searchStatsItems.value,
    syntaxItems: syntaxItems.value,
  }))

  const heroEvents = {
    applySyntax,
  }

  const contentBindings = computed(() => ({
    filterCatalogLoadError: filterCatalogLoadError.value,
    normalizedQuery: normalizedQuery.value,
    idleStateText: idleStateText.value,
    loading: loading.value,
    loadingStateText: loadingStateText.value,
    isEmpty: isEmpty.value,
    emptyStateText: emptyStateText.value,
    visibleSearchSections: visibleSearchSections.value,
    searchType: searchType.value,
    totalPages: totalPages.value,
    page: page.value,
  }))

  const contentEvents = {
    changePage,
    changeType,
    openSearchResult,
  }

  return {
    contentBindings,
    contentEvents,
    heroBindings,
    heroEvents,
    sidebarBindings,
    sidebarEvents,
  }
}

export function useSearchResultsViewBindings(options) {
  return createSearchResultsViewBindings(options)
}
