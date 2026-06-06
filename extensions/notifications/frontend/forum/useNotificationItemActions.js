export function createNotificationItemActions({
  getNotificationErrorMessage,
  getNotificationUiCopy,
  modalStore,
  notificationStore,
  notifications,
  resolvePath,
  router,
}) {
  async function markAsRead(notificationId) {
    try {
      await notificationStore.markAsRead(notificationId)
      const notification = notifications().find(item => item.id === notificationId)
      if (notification) {
        notification.is_read = true
      }
    } catch (error) {
      console.error('标记失败:', error)
    }
  }

  async function deleteNotification(notificationId) {
    const confirmed = await modalStore.confirm({
      title: getNotificationUiCopy('notification-confirm-delete-title', {}, '删除通知'),
      message: getNotificationUiCopy('notification-confirm-delete-message', {}, '确定要删除这条通知吗？'),
      confirmText: getNotificationUiCopy('notification-confirm-delete-confirm', {}, '删除'),
      cancelText: getNotificationUiCopy('notification-confirm-cancel', {}, '取消'),
      tone: 'danger'
    })
    if (!confirmed) return

    try {
      await notificationStore.deleteNotification(notificationId)
    } catch (error) {
      console.error('删除失败:', error)
      await modalStore.alert({
        title: getNotificationUiCopy('notification-alert-delete-failed-title', {}, '删除失败'),
        message: getNotificationErrorMessage(error),
        tone: 'danger'
      })
    }
  }

  async function handleNotificationClick(notification) {
    if (!notification.is_read) {
      await markAsRead(notification.id)
    }

    router.push(await resolvePath(notification))
  }

  return {
    deleteNotification,
    handleNotificationClick,
    markAsRead,
  }
}

export function useNotificationItemActions({
  getNotificationErrorMessage,
  getNotificationUiCopy,
  modalStore,
  notificationStore,
  notifications,
  resolvePath,
  router,
}) {
  return createNotificationItemActions({
    getNotificationErrorMessage,
    getNotificationUiCopy,
    modalStore,
    notificationStore,
    notifications: () => notifications.value,
    resolvePath,
    router,
  })
}
