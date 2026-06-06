import { usePaginatedListState } from '@bias/forum'
import { ref } from '@bias/forum'

export function createNotificationLoadState({
  fetchNotifications,
  getActiveType,
  getCurrentPage,
  getNotifications,
  getUnreadOnly,
  listStateFactory,
}) {
  const totalPages = ref(1)
  const totalCount = ref(0)

  function applyTotals(data = {}) {
    const notifications = getNotifications()
    totalCount.value = Number(data.total || notifications.length || 0)
    totalPages.value = Math.max(1, Math.ceil((data.total || notifications.length || 0) / (data.limit || 20)))
  }

  async function loadNotifications() {
    const data = await fetchNotifications({
      page: getCurrentPage(),
      ...(getActiveType() ? { type: getActiveType() } : {}),
      ...(getUnreadOnly() ? { is_read: false } : {}),
    })

    applyTotals(data)
    return data
  }

  const listState = listStateFactory({
    load: loadNotifications,
  })

  return {
    listState,
    loadNotifications,
    totalCount,
    totalPages,
  }
}

export function useNotificationLoadState({
  activeType,
  currentPage,
  notificationStore,
  notifications,
  unreadOnly,
}) {
  return createNotificationLoadState({
    async fetchNotifications(params) {
      return notificationStore.fetchNotifications(params)
    },
    getActiveType() {
      return activeType.value
    },
    getCurrentPage() {
      return currentPage.value
    },
    getNotifications() {
      return notifications.value
    },
    getUnreadOnly() {
      return unreadOnly.value
    },
    listStateFactory({ load }) {
      return usePaginatedListState({
        watchSources: () => [currentPage.value, activeType.value, unreadOnly.value],
        initialLoading: true,
        load,
      })
    },
  })
}
