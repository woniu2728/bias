export function createNotificationBulkActions({
  activeType,
  filteredReadCount,
  filteredUnreadCount,
  getNotificationUiCopy,
  hasActiveFilter,
  listState,
  modalStore,
  notificationStore,
  setBusy,
  showNotificationActionError,
}) {
  async function refreshNotifications() {
    await listState.refresh({
      mode: 'initial',
      forceLoading: true,
    })
  }

  async function markAllAsRead() {
    const unreadCount = filteredUnreadCount()
    if (unreadCount === 0) return

    const confirmed = await modalStore.confirm({
      title: getNotificationUiCopy(
        'notification-confirm-mark-all-title',
        { hasActiveFilter: hasActiveFilter() },
        hasActiveFilter() ? '标记当前筛选结果为已读' : '全部标记为已读'
      ),
      message: getNotificationUiCopy(
        'notification-confirm-mark-all-message',
        { hasActiveFilter: hasActiveFilter(), unreadCount },
        hasActiveFilter()
          ? `确定将当前筛选结果中的 ${unreadCount} 条未读通知标记为已读吗？`
          : `确定将当前 ${unreadCount} 条未读通知标记为已读吗？`
      ),
      confirmText: getNotificationUiCopy('notification-confirm-mark-all-confirm', {}, '标记已读'),
      cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
      tone: 'primary'
    })
    if (!confirmed) return

    setBusy(true)
    try {
      if (hasActiveFilter()) {
        await notificationStore.markFilteredAsRead({
          type: activeType(),
        })
      } else {
        await notificationStore.markAllAsRead()
      }
      await refreshNotifications()
      await modalStore.alert({
        title: getNotificationUiCopy('notification-alert-mark-all-success-title', {}, '已全部标记为已读'),
        message: getNotificationUiCopy(
          'notification-alert-mark-all-success-message',
          { hasActiveFilter: hasActiveFilter() },
          hasActiveFilter() ? '当前筛选范围内的未读通知已更新为已读。' : '当前页面的未读通知已更新为已读。'
        ),
        tone: 'success'
      })
    } catch (error) {
      console.error('标记失败:', error)
      await showNotificationActionError(error)
    } finally {
      setBusy(false)
    }
  }

  async function clearReadNotifications() {
    const readCount = filteredReadCount()
    if (readCount === 0) return

    const confirmed = await modalStore.confirm({
      title: getNotificationUiCopy(
        'notification-confirm-clear-read-title',
        { hasActiveFilter: hasActiveFilter() },
        hasActiveFilter() ? '清除当前筛选中的已读通知' : '清除当前页已读通知'
      ),
      message: getNotificationUiCopy(
        'notification-confirm-clear-read-message',
        { hasActiveFilter: hasActiveFilter(), readCount },
        hasActiveFilter()
          ? `确定清除当前筛选结果中的 ${readCount} 条已读通知吗？`
          : `确定清除当前页中的 ${readCount} 条已读通知吗？`
      ),
      confirmText: getNotificationUiCopy('notification-confirm-clear-read-confirm', {}, '清除已读'),
      cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
      tone: 'danger'
    })
    if (!confirmed) return

    setBusy(true)
    try {
      if (hasActiveFilter()) {
        await notificationStore.clearFilteredReadNotifications({
          type: activeType(),
        })
      } else {
        await notificationStore.clearReadNotifications()
      }
      await refreshNotifications()
      await modalStore.alert({
        title: getNotificationUiCopy('notification-alert-clear-read-success-title', {}, '已清除已读通知'),
        message: getNotificationUiCopy('notification-alert-clear-read-success-message', {}, '当前范围内的已读通知已清除。'),
        tone: 'success'
      })
    } catch (error) {
      console.error('清除失败:', error)
      await showNotificationActionError(error)
    } finally {
      setBusy(false)
    }
  }

  async function markGroupAsRead(group) {
    const discussionId = Number(group?.discussionId || 0)
    const unreadCount = Array.isArray(group?.items) ? group.items.filter(item => !item.is_read).length : 0
    if (!discussionId || unreadCount === 0) return

    const confirmed = await modalStore.confirm({
      title: getNotificationUiCopy('notification-confirm-mark-group-title', {}, '标记该讨论通知为已读'),
      message: getNotificationUiCopy(
        'notification-confirm-mark-group-message',
        { groupTitle: group.title, unreadCount },
        `确定将“${group.title}”下的 ${unreadCount} 条未读通知标记为已读吗？`
      ),
      confirmText: getNotificationUiCopy('notification-confirm-mark-all-confirm', {}, '标记已读'),
      cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
      tone: 'primary'
    })
    if (!confirmed) return

    setBusy(true)
    try {
      await notificationStore.markFilteredAsRead({
        type: activeType(),
        discussionId,
      })
      await refreshNotifications()
    } catch (error) {
      console.error('分组标记失败:', error)
      await showNotificationActionError(error)
    } finally {
      setBusy(false)
    }
  }

  async function clearGroupReadNotifications(group) {
    const discussionId = Number(group?.discussionId || 0)
    const readCount = Array.isArray(group?.items) ? group.items.filter(item => item.is_read).length : 0
    if (!discussionId || readCount === 0) return

    const confirmed = await modalStore.confirm({
      title: getNotificationUiCopy('notification-confirm-clear-group-title', {}, '清除该讨论中的已读通知'),
      message: getNotificationUiCopy(
        'notification-confirm-clear-group-message',
        { groupTitle: group.title, readCount },
        `确定清除“${group.title}”下的 ${readCount} 条已读通知吗？`
      ),
      confirmText: getNotificationUiCopy('notification-confirm-clear-read-confirm', {}, '清除已读'),
      cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
      tone: 'danger'
    })
    if (!confirmed) return

    setBusy(true)
    try {
      await notificationStore.clearFilteredReadNotifications({
        type: activeType(),
        discussionId,
      })
      await refreshNotifications()
    } catch (error) {
      console.error('分组清除失败:', error)
      await showNotificationActionError(error)
    } finally {
      setBusy(false)
    }
  }

  return {
    clearGroupReadNotifications,
    clearReadNotifications,
    markAllAsRead,
    markGroupAsRead,
  }
}

export function useNotificationBulkActions({
  activeType,
  filteredReadCount,
  filteredUnreadCount,
  getNotificationUiCopy,
  hasActiveFilter,
  listState,
  marking,
  modalStore,
  notificationStore,
  showNotificationActionError,
}) {
  return createNotificationBulkActions({
    activeType: () => activeType.value,
    filteredReadCount: () => filteredReadCount.value,
    filteredUnreadCount: () => filteredUnreadCount.value,
    getNotificationUiCopy,
    hasActiveFilter: () => hasActiveFilter.value,
    listState,
    modalStore,
    notificationStore,
    setBusy(value) {
      marking.value = value
    },
    showNotificationActionError,
  })
}
