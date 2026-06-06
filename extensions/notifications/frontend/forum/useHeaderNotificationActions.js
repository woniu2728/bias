export function createHeaderNotificationActions({
  getNotificationErrorMessage,
  getNotificationUiCopy,
  hasReadNotifications,
  modalStore,
  notificationStore,
  resolvePath,
  router,
  setActionMessage,
  setActionTone,
  setClearingRead,
  setMarkingAllRead,
  setShowNotifications,
  showHeaderNotificationError,
  showNotifications,
}) {
  async function refreshMenuNotifications() {
    await notificationStore.fetchNotifications({ limit: 8 })
  }

  async function toggleNotifications() {
    const nextOpen = !showNotifications()
    setShowNotifications(nextOpen)

    if (!nextOpen) return

    setActionMessage('')

    try {
      await refreshMenuNotifications()
    } catch (error) {
      console.error('加载通知失败:', error)
    }
  }

  async function markAllNotificationsAsRead() {
    setMarkingAllRead(true)

    try {
      const result = await notificationStore.markAllAsRead()
      await refreshMenuNotifications()
      setActionTone('success')
      setActionMessage(
        result?.message || getNotificationUiCopy('notifications-menu-mark-all-success', {}, '已全部标记为已读')
      )
    } catch (error) {
      console.error('全部标记已读失败:', error)
      setActionTone('danger')
      setActionMessage(
        getNotificationErrorMessage(
          error,
          getNotificationUiCopy('notifications-menu-mark-all-error', {}, '全部标记已读失败')
        )
      )
      await showHeaderNotificationError?.(error)
    } finally {
      setMarkingAllRead(false)
    }
  }

  async function clearReadNotifications() {
    if (!hasReadNotifications()) return

    const confirmed = modalStore
      ? await modalStore.confirm({
        title: getNotificationUiCopy('notifications-menu-clear-read-confirm-title', {}, '清除已读通知'),
        message: getNotificationUiCopy('notifications-menu-clear-read-confirm-message', {}, '确定要清除所有已读通知吗？未读通知会保留。'),
        confirmText: getNotificationUiCopy('notifications-menu-clear-read-confirm-confirm', {}, '清除'),
        cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
        tone: 'danger'
      })
      : true
    if (!confirmed) return

    setClearingRead(true)

    try {
      const result = await notificationStore.clearReadNotifications()
      await refreshMenuNotifications()
      setActionTone('success')
      setActionMessage(
        result?.message || getNotificationUiCopy('notifications-menu-clear-read-success', {}, '已清除已读通知')
      )
    } catch (error) {
      console.error('清除已读通知失败:', error)
      setActionTone('danger')
      setActionMessage(
        getNotificationErrorMessage(
          error,
          getNotificationUiCopy('notifications-menu-clear-read-error', {}, '清除已读通知失败')
        )
      )
      await showHeaderNotificationError?.(error)
    } finally {
      setClearingRead(false)
    }
  }

  async function handleNotificationClick(notification) {
    try {
      if (!notification.is_read) {
        await notificationStore.markAsRead(notification.id)
      }
    } catch (error) {
      console.error('标记通知已读失败:', error)
    }

    setShowNotifications(false)
    router.push(await resolvePath(notification))
  }

  function closeNotifications() {
    setShowNotifications(false)
  }

  function openNotificationGroup(group) {
    closeNotifications()
    router.push(group.discussionId ? `/d/${group.discussionId}` : '/notifications')
  }

  function openNotificationsPage() {
    closeNotifications()
    router.push('/notifications')
  }

  function openNotificationsPageByType(type) {
    closeNotifications()
    router.push(type ? `/notifications?type=${encodeURIComponent(type)}` : '/notifications')
  }

  return {
    clearReadNotifications,
    closeNotifications,
    handleNotificationClick,
    markAllNotificationsAsRead,
    openNotificationGroup,
    openNotificationsPage,
    openNotificationsPageByType,
    toggleNotifications,
  }
}

export function useHeaderNotificationActions({
  actionMessage,
  actionTone,
  clearingRead,
  getNotificationErrorMessage,
  getNotificationUiCopy,
  hasReadNotifications,
  markingAllRead,
  modalStore,
  notificationStore,
  resolvePath,
  router,
  showHeaderNotificationError,
  showNotifications,
}) {
  return createHeaderNotificationActions({
    getNotificationErrorMessage,
    getNotificationUiCopy,
    hasReadNotifications: () => hasReadNotifications.value,
    modalStore,
    notificationStore,
    resolvePath,
    router,
    setActionMessage(value) {
      actionMessage.value = value
    },
    setActionTone(value) {
      actionTone.value = value
    },
    setClearingRead(value) {
      clearingRead.value = value
    },
    setMarkingAllRead(value) {
      markingAllRead.value = value
    },
    setShowNotifications(value) {
      showNotifications.value = value
    },
    showHeaderNotificationError,
    showNotifications: () => showNotifications.value,
  })
}
