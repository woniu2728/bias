export function useDiscussionListRouteActions({
  routeState,
  listFilter,
  searchQuery,
  sortBy,
}) {
  async function changeSortBy(sort) {
    if (sortBy.value === sort) return
    await routeState.push({
      sortBy: sort,
      listFilter: listFilter.value,
      searchQuery: searchQuery.value,
    })
  }

  async function changeListFilter(filterCode) {
    if (listFilter.value === filterCode) return
    await routeState.push({
      listFilter: filterCode,
      sortBy: sortBy.value,
      searchQuery: searchQuery.value,
    })
  }

  async function changeSearchQuery(nextQuery) {
    if (searchQuery.value === nextQuery) return
    await routeState.push({
      searchQuery: nextQuery,
      sortBy: sortBy.value,
      listFilter: listFilter.value,
    })
  }

  return {
    changeListFilter,
    changeSearchQuery,
    changeSortBy,
  }
}
