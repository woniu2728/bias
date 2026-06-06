import { getUiCopy } from '@bias/forum'
import {
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
} from '@bias/forum'
import {
  getNotificationIconClass,
  getNotificationPresentationModel,
  getNotificationTextHtml,
} from './notificationRuntime.js'
import {
  useStartDiscussionAction,
} from '@bias/forum'
import { computed, watch } from '@bias/forum'
import { resolveNotificationMetaPayload } from './notificationMeta.js'
import { useNotificationPage } from './useNotificationPage.js'
import { useNotificationViewBindings } from './useNotificationViewBindings.js'

export function useNotificationViewModel({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  notificationStore,
  pageState: injectedPageState,
  route,
  router,
}) {
  const pageState = injectedPageState || useNotificationPage({
    modalStore,
    notificationStore,
    route,
    router,
  })
  const { startDiscussion } = useStartDiscussionAction({
    authStore,
    composerStore,
    router,
  })

  const activeNotificationLabel = computed(() => {
    const activeItem = pageState.notificationTypeItems.value.find(item => item.value === pageState.activeType.value)
    return getUiCopy({
      surface: 'notification-page-active-filter-label',
      label: activeItem?.label || '',
      value: pageState.activeType.value,
    })?.text || activeItem?.label || '全部通知'
  })

  const heroTitleText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-hero-title',
    })?.text || '通知'
  })

  const heroPillText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-hero-pill',
    })?.text || '消息中心'
  })

  const heroDescriptionText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-hero-description',
    })?.text || '这里会显示回复、提及、点赞、审核和账号状态相关通知。'
  })

  const markAllButtonText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-mark-all',
      marking: pageState.marking.value,
      hasActiveFilter: pageState.hasActiveFilter.value,
    })?.text || (pageState.marking.value
      ? '处理中...'
      : (pageState.hasActiveFilter.value ? '当前筛选标记已读' : '全部标记为已读'))
  })

  const clearReadButtonText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-clear-read',
      marking: pageState.marking.value,
      hasActiveFilter: pageState.hasActiveFilter.value,
    })?.text || (pageState.marking.value
      ? '处理中...'
      : (pageState.hasActiveFilter.value ? '当前筛选清除已读' : '当前页清除已读'))
  })

  const unreadToggleText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-unread-toggle',
      unreadOnly: pageState.unreadOnly.value,
    })?.text || (pageState.unreadOnly.value ? '查看全部通知' : '仅看未读')
  })

  const preferencesLinkText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-preferences-link',
    })?.text || '通知偏好前往个人设置'
  })

  const filterDescriptionText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-filter-description',
    })?.text || '按通知类型筛选消息流，方便集中处理提及、点赞、审核和账号状态通知。'
  })

  const openDiscussionText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-open-discussion',
    })?.text || '打开讨论'
  })

  const markGroupReadText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-mark-group-read',
    })?.text || '整组标记已读'
  })

  const clearGroupReadText = computed(() => {
    return getUiCopy({
      surface: 'notification-page-clear-group-read',
    })?.text || '整组清理已读'
  })

  watch(
    () => [
      activeNotificationLabel.value,
      pageState.activeType.value,
      pageState.currentPage.value,
      pageState.unreadOnly.value,
      pageState.viewMode.value,
    ],
    () => {
      forumStore.setPageMeta(resolveNotificationMetaPayload({
        activeLabel: activeNotificationLabel.value,
        activeType: pageState.activeType.value,
        currentPage: pageState.currentPage.value,
        unreadOnly: pageState.unreadOnly.value,
        viewMode: pageState.viewMode.value,
      }))
    },
    { immediate: true }
  )

  function groupCountText(count) {
    return getUiCopy({
      surface: 'notification-page-group-count',
      count,
    })?.text || `${count} 条通知`
  }

  function handleStartDiscussion() {
    startDiscussion({
      source: 'notifications',
    })
  }

  function formatDate(dateString) {
    return formatRelativeTime(dateString)
  }

  function getNotificationMessageHtml(notification) {
    return getNotificationTextHtml(notification)
  }

  function getNotificationPresentation(notification) {
    return getNotificationPresentationModel(notification)
  }

  function getNotificationAvatarInitial(notification) {
    return getUserInitial(notification.from_user || {})
  }

  function getNotificationAvatarColor(notification) {
    return getUserAvatarColor(notification.from_user || {})
  }

  const viewBindings = useNotificationViewBindings({
    activeNotificationLabel,
    activeType: pageState.activeType,
    authStore,
    changePage: pageState.changePage,
    changeType: pageState.changeType,
    changeViewMode: pageState.changeViewMode,
    clearGroupReadNotifications: pageState.clearGroupReadNotifications,
    clearGroupReadText,
    clearReadButtonText,
    clearReadNotifications: pageState.clearReadNotifications,
    currentPage: pageState.currentPage,
    deleteNotification: pageState.deleteNotification,
    emptyStateText: pageState.emptyStateText,
    filterDescriptionText,
    filteredReadCount: pageState.filteredReadCount,
    filteredUnreadCount: pageState.filteredUnreadCount,
    formatDate,
    getNotificationAvatarColor,
    getNotificationAvatarInitial,
    getNotificationIconClass,
    getNotificationMessageHtml,
    getNotificationPresentation,
    getUserDisplayName,
    groupedNotifications: pageState.groupedNotifications,
    groupCountText,
    handleNotificationClick: pageState.handleNotificationClick,
    handleStartDiscussion,
    heroDescriptionText,
    heroPillText,
    heroTitleText,
    loadError: pageState.loadError,
    loading: pageState.loading,
    loadingStateText: pageState.loadingStateText,
    markAllAsRead: pageState.markAllAsRead,
    markAllButtonText,
    markAsRead: pageState.markAsRead,
    marking: pageState.marking,
    markGroupAsRead: pageState.markGroupAsRead,
    markGroupReadText,
    notificationStore,
    notificationTypeItems: pageState.notificationTypeItems,
    notifications: pageState.notifications,
    openDiscussionText,
    preferencesLinkText,
    router,
    toggleUnreadOnly: pageState.toggleUnreadOnly,
    totalPages: pageState.totalPages,
    unreadToggleText,
    viewMode: pageState.viewMode,
    viewModeItems: pageState.viewModeItems,
  })

  return {
    ...pageState,
    activeNotificationLabel,
    clearGroupReadText,
    clearReadButtonText,
    filterDescriptionText,
    groupCountText,
    heroDescriptionText,
    heroPillText,
    heroTitleText,
    markAllButtonText,
    markGroupReadText,
    openDiscussionText,
    preferencesLinkText,
    unreadToggleText,
    formatDate,
    getNotificationAvatarColor,
    getNotificationAvatarInitial,
    getNotificationIconClass,
    getNotificationMessageHtml,
    getNotificationPresentation,
    getUserDisplayName,
    handleStartDiscussion,
    ...viewBindings,
  }
}
