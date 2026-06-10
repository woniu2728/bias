import {
  ref,
  computed,
  useRoutePagination } from '@bias/core'
import { getEmptyState,
  getStateBlock,
  getUiCopy
} from '@bias/forum'
import {
  getResolvedNotificationTypes,
  resolveNotificationPath,
  useNotificationGroups,
} from './notificationRuntime.js'
import { useNotificationBulkActions } from './useNotificationBulkActions.js'
import { useNotificationDisplayState } from './useNotificationDisplayState.js'
import { useNotificationItemActions } from './useNotificationItemActions.js'
import { useNotificationLoadState } from './useNotificationLoadState.js'
import { useNotificationRouteActions } from './useNotificationRouteActions.js'
import { useNotificationRouteState } from './useNotificationRouteState.js'

export function useNotificationPage({
  modalStore,
  notificationStore,
  route,
  router
}) {
  const routeState = useNotificationRouteState({ route, router })
  const marking = ref(false)
  const activeType = routeState.activeType
  const currentPage = routeState.currentPage
  const unreadOnly = routeState.unreadOnly
  const viewMode = routeState.viewMode
  const routePagination = useRoutePagination({
    page: currentPage,
    push: routeState.push,
    pageStateKey: 'currentPage',
  })
  const routeActions = useNotificationRouteActions({
    activeType,
    currentPage,
    routePagination,
    unreadOnly,
    viewMode,
  })
  const notifications = computed(() => notificationStore.notifications)
  const loadState = useNotificationLoadState({
    activeType,
    currentPage,
    notificationStore,
    notifications,
    unreadOnly,
  })
  const groupedNotifications = useNotificationGroups(notifications, '论坛')
  const filteredUnreadCount = computed(() => notifications.value.filter(item => !item.is_read).length)
  const filteredReadCount = computed(() => notifications.value.length - filteredUnreadCount.value)
  const hasActiveFilter = computed(() => unreadOnly.value || Boolean(activeType.value))
  const loading = loadState.listState.loading
  const loadError = loadState.listState.loadError
  const displayState = useNotificationDisplayState({
    activeType,
    getEmptyStateText(context) {
      return getEmptyState(context)?.text || ''
    },
    getNotificationUiCopy,
    getRegistryUiCopy(context) {
      return getUiCopy(context)?.text || ''
    },
    getResolvedTypes: getResolvedNotificationTypes,
    getStateBlockText(context) {
      return getStateBlock(context)?.text || ''
    },
    loading,
    notificationStore,
    notifications,
    totalCount: loadState.totalCount,
    unreadOnly,
  })

  function getNotificationUiCopy(surface, context = {}, fallback = '') {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  function getNotificationErrorMessage(error, fallback = getNotificationUiCopy('notification-error-retry-message', {}, '请稍后重试')) {
    return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
  }

  async function showNotificationActionError(error, titleFallback = '操作失败') {
    await modalStore.alert({
      title: getNotificationUiCopy('notification-alert-action-failed-title', {}, titleFallback),
      message: getNotificationErrorMessage(error),
      tone: 'danger'
    })
  }

  const bulkActions = useNotificationBulkActions({
    activeType,
    filteredReadCount,
    filteredUnreadCount,
    getNotificationUiCopy,
    hasActiveFilter,
    listState: loadState.listState,
    marking,
    modalStore,
    notificationStore,
    showNotificationActionError,
  })
  const itemActions = useNotificationItemActions({
    getNotificationErrorMessage,
    getNotificationUiCopy,
    modalStore,
    notificationStore,
    notifications,
    resolvePath: resolveNotificationPath,
    router,
  })

  return {
    notifications,
    emptyStateText: displayState.emptyStateText,
    loadingStateText: displayState.loadingStateText,
    loading,
    loadError,
    marking,
    currentPage,
    totalPages: loadState.totalPages,
    activeType,
    unreadOnly,
    viewMode,
    filteredUnreadCount,
    filteredReadCount,
    hasActiveFilter,
    notificationTypeItems: displayState.notificationTypeItems,
    viewModeItems: displayState.viewModeItems,
    groupedNotifications,
    markAsRead: itemActions.markAsRead,
    markAllAsRead: bulkActions.markAllAsRead,
    clearReadNotifications: bulkActions.clearReadNotifications,
    markGroupAsRead: bulkActions.markGroupAsRead,
    clearGroupReadNotifications: bulkActions.clearGroupReadNotifications,
    deleteNotification: itemActions.deleteNotification,
    handleNotificationClick: itemActions.handleNotificationClick,
    changeType: routeActions.changeType,
    changeViewMode: routeActions.changeViewMode,
    toggleUnreadOnly: routeActions.toggleUnreadOnly,
    changePage: routeActions.changePage
  }
}
