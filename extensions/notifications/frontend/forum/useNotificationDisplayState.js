import { computed } from '@bias/core'


export function createNotificationDisplayState({
  activeType,
  getEmptyStateText = null,
  getNotificationUiCopy,
  getRegistryUiCopy = null,
  getResolvedTypes = () => [],
  getStateBlockText = null,
  getTotalCount,
  getTypeCounts,
  getUnreadOnly,
  getUnreadTypeCounts,
  loading,
  notifications,
}) {
  const emptyStateText = computed(() => {
    return getEmptyStateText?.({
      surface: 'notifications-page-empty',
      notifications: notifications(),
      unreadOnly: getUnreadOnly(),
      activeType: activeType(),
    }) || '暂无通知'
  })

  const loadingStateText = computed(() => {
    return getStateBlockText?.({
      surface: 'notifications-page-loading',
      loading: loading(),
      activeType: activeType(),
      unreadOnly: getUnreadOnly(),
    }) || '正在加载通知...'
  })

  function formatSummaryCount() {
    const count = getUnreadOnly()
      ? notifications().length
      : (getTotalCount() || notifications().length || 0)

    return getNotificationUiCopy(
      'notification-summary-count',
      {
        unreadOnly: getUnreadOnly(),
        count,
      },
      getUnreadOnly()
        ? `${notifications().length || 0} 未读`
        : String(count)
    )
  }

  function formatTypeCount(type) {
    const total = Number(getTypeCounts()?.[type] || 0)
    const unread = Number(getUnreadTypeCounts()?.[type] || 0)
    return getNotificationUiCopy(
      'notification-type-count',
      {
        total,
        unread,
        type,
      },
      unread > 0 ? `${total} / ${unread} 未读` : String(total)
    )
  }

  const notificationTypeItems = computed(() => {
    const registeredItems = getResolvedTypes().map(item => ({
      value: item.type,
      label: item.label,
      count: formatTypeCount(item.type),
    }))

    return [
      {
        value: '',
        label: getRegistryUiCopy?.({
          surface: 'notification-filter-all-label',
          count: formatSummaryCount(),
        }) || '全部通知',
        count: formatSummaryCount(),
      },
      ...registeredItems,
    ]
  })

  const viewModeItems = computed(() => {
    return [
      {
        value: 'timeline',
        label: getRegistryUiCopy?.({
          surface: 'notification-view-mode-timeline',
        }) || '时间流',
      },
      {
        value: 'grouped',
        label: getRegistryUiCopy?.({
          surface: 'notification-view-mode-grouped',
        }) || '按讨论分组',
      },
    ]
  })

  return {
    emptyStateText,
    formatSummaryCount,
    formatTypeCount,
    loadingStateText,
    notificationTypeItems,
    viewModeItems,
  }
}

export function useNotificationDisplayState({
  activeType,
  getEmptyStateText,
  getNotificationUiCopy,
  getRegistryUiCopy,
  getResolvedTypes,
  getStateBlockText,
  loading,
  notificationStore,
  notifications,
  totalCount,
  unreadOnly,
}) {
  return createNotificationDisplayState({
    activeType: () => activeType.value,
    getEmptyStateText,
    getNotificationUiCopy,
    getRegistryUiCopy,
    getResolvedTypes,
    getStateBlockText,
    getTotalCount: () => totalCount.value,
    getTypeCounts: () => notificationStore.typeCounts,
    getUnreadOnly: () => unreadOnly.value,
    getUnreadTypeCounts: () => notificationStore.unreadTypeCounts,
    loading: () => loading.value,
    notifications: () => notifications.value,
  })
}
