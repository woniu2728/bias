import {
  getEmptyState,
  getStateBlock,
  getUiCopy
} from '@bias/forum'
import { ref } from '@bias/core'
import {
  getNotificationPresentationModel,
  getResolvedNotificationTypes,
  resolveNotificationPath,
  useNotificationGroups
} from './notificationRuntime.js'
import { useHeaderNotificationActions } from './useHeaderNotificationActions.js'
import { createHeaderNotificationDisplayState } from './useHeaderNotificationDisplayState.js'

export function useHeaderNotifications({
  modalStore,
  notificationStore,
  forumTitle,
  router
}) {
  const showNotifications = ref(false)
  const actionMessage = ref('')
  const actionTone = ref('info')
  const markingAllRead = ref(false)
  const clearingRead = ref(false)
  const {
    notificationItems,
    hasReadNotifications,
    notificationGroups,
    notificationTypeSummaries,
    emptyStateText,
    loadingStateText,
  } = createHeaderNotificationDisplayState({
    createNotificationGroups(notificationItems) {
      return useNotificationGroups(notificationItems, forumTitle || '论坛')
    },
    getEmptyStateText(notificationItems) {
      return getEmptyState({
        surface: 'notifications-menu-empty',
        notifications: notificationItems,
      })?.text || '暂无通知'
    },
    getLoadingStateText(notificationItems) {
      return getStateBlock({
        surface: 'notifications-menu-loading',
        loading: notificationStore.loading,
        notifications: notificationItems,
      })?.text || '加载中...'
    },
    getReadCount: () => notificationStore.readCount,
    getResolvedTypes: getResolvedNotificationTypes,
    getTypeCounts: () => notificationStore.typeCounts,
    getUnreadTypeCounts: () => notificationStore.unreadTypeCounts,
    notifications: () => notificationStore.notifications,
  })

  function getNotificationUiCopy(surface, context = {}, fallback = '') {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  function getNotificationErrorMessage(error, fallback = getNotificationUiCopy('notifications-menu-action-retry-message', {}, '请稍后重试')) {
    return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
  }

  async function showHeaderNotificationError(error, fallback = '操作失败') {
    if (!modalStore) return

    await modalStore.alert({
      title: getNotificationUiCopy('notifications-menu-action-failed-title', {}, fallback),
      message: getNotificationErrorMessage(error),
      tone: 'danger'
    })
  }

  function getNotificationPresentation(notification) {
    return getNotificationPresentationModel(notification)
  }

  const {
    toggleNotifications,
    markAllNotificationsAsRead,
    clearReadNotifications,
    handleNotificationClick,
    openNotificationGroup,
    openNotificationsPage,
    openNotificationsPageByType,
    closeNotifications,
  } = useHeaderNotificationActions({
    actionMessage,
    actionTone,
    clearingRead,
    getNotificationErrorMessage,
    getNotificationUiCopy,
    hasReadNotifications,
    markingAllRead,
    modalStore,
    notificationStore,
    resolvePath: resolveNotificationPath,
    router,
    showHeaderNotificationError,
    showNotifications,
  })

  return {
    showNotifications,
    notificationItems,
    hasReadNotifications,
    notificationGroups,
    notificationTypeSummaries,
    emptyStateText,
    loadingStateText,
    actionMessage,
    actionTone,
    markingAllRead,
    clearingRead,
    getNotificationPresentation,
    toggleNotifications,
    markAllNotificationsAsRead,
    clearReadNotifications,
    handleNotificationClick,
    openNotificationGroup,
    openNotificationsPage,
    openNotificationsPageByType,
    closeNotifications
  }
}
