export function useNotificationRouteActions({
  activeType,
  currentPage,
  routePagination,
  unreadOnly,
  viewMode,
}) {
  async function changeType(type) {
    const nextType = typeof type === 'string' ? type.trim() : ''
    if (nextType === activeType.value) {
      return false
    }

    await routePagination.resetPage({
      activeType: nextType,
    })

    return true
  }

  async function toggleUnreadOnly() {
    await routePagination.resetPage({
      unreadOnly: !unreadOnly.value,
    })

    return true
  }

  async function changeViewMode(mode) {
    const nextMode = mode === 'grouped' ? 'grouped' : 'timeline'
    if (nextMode === viewMode.value) {
      return false
    }

    await routePagination.resetPage({
      viewMode: nextMode,
    })

    return true
  }

  async function changePage(page) {
    return routePagination.changePage(page, {
      scroll: false,
    })
  }

  return {
    changePage,
    changeType,
    changeViewMode,
    currentPage,
    toggleUnreadOnly,
  }
}
