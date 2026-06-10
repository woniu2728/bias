export function useSearchResultsRouteActions({
  appendFilter,
  normalizedQuery,
  routePagination,
  searchSources,
  searchType,
}) {
  const allowedTypes = ['all', ...searchSources.map(item => item.routeType || item.type)]

  async function changeType(type) {
    const nextType = allowedTypes.includes(type) ? type : 'all'
    if (nextType === searchType.value) {
      return false
    }

    await routePagination.resetPage({
      searchType: nextType,
    })

    return true
  }

  async function changePage(nextPage) {
    return routePagination.changePage(nextPage)
  }

  async function applySyntax(syntax) {
    const nextQuery = appendFilter(normalizedQuery.value, syntax)
    if (nextQuery === normalizedQuery.value) {
      return false
    }

    await routePagination.resetPage({
      normalizedQuery: nextQuery,
    })

    return true
  }

  return {
    applySyntax,
    changePage,
    changeType,
  }
}
