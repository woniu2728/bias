import { computed } from '@bias/core'


export function createHeaderNotificationDisplayState({
  createNotificationGroups = () => ({ value: [] }),
  getEmptyStateText,
  getLoadingStateText,
  getReadCount,
  getResolvedTypes = () => [],
  getTypeCounts,
  getUnreadTypeCounts,
  notifications,
}) {
  const notificationItems = computed(() => notifications().slice(0, 8))
  const hasReadNotifications = computed(() => getReadCount() > 0)
  const notificationGroups = createNotificationGroups(notificationItems)

  const notificationTypeSummaries = computed(() => {
    return getResolvedTypes()
      .map(item => ({
        type: item.type,
        label: item.label,
        total: Number(getTypeCounts()?.[item.type] || 0),
        unread: Number(getUnreadTypeCounts()?.[item.type] || 0),
      }))
      .filter(item => item.total > 0 || item.unread > 0)
      .slice(0, 4)
  })

  const emptyStateText = computed(() => {
    return getEmptyStateText?.(notificationItems.value) || '暂无通知'
  })

  const loadingStateText = computed(() => {
    return getLoadingStateText?.(notificationItems.value) || '加载中...'
  })

  return {
    emptyStateText,
    hasReadNotifications,
    loadingStateText,
    notificationGroups,
    notificationItems,
    notificationTypeSummaries,
  }
}
