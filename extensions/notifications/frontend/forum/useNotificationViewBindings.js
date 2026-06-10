import { computed } from '@bias/core'


export function createNotificationViewBindings({
  activeNotificationLabel,
  activeType,
  authStore,
  changePage,
  changeType,
  changeViewMode,
  clearGroupReadNotifications,
  clearGroupReadText,
  clearReadButtonText,
  clearReadNotifications,
  currentPage,
  deleteNotification,
  emptyStateText,
  filterDescriptionText,
  filteredReadCount,
  filteredUnreadCount,
  formatDate,
  getNotificationAvatarColor,
  getNotificationAvatarInitial,
  getNotificationIconClass,
  getNotificationMessageHtml,
  getNotificationPresentation,
  getUserDisplayName,
  groupedNotifications,
  groupCountText,
  handleNotificationClick,
  handleStartDiscussion,
  heroDescriptionText,
  heroPillText,
  heroTitleText,
  loadError,
  loading,
  loadingStateText,
  markAllAsRead,
  markAllButtonText,
  markAsRead,
  marking,
  markGroupAsRead,
  markGroupReadText,
  notificationStore,
  notificationTypeItems,
  notifications,
  openDiscussionText,
  preferencesLinkText,
  router,
  toggleUnreadOnly,
  totalPages,
  unreadToggleText,
  viewMode,
  viewModeItems,
}) {
  const sidebarBindings = computed(() => ({
    authStore,
    notificationStore,
    showStartDiscussionButton: !authStore.isAuthenticated || authStore.canStartDiscussion,
  }))

  const sidebarEvents = {
    startDiscussion: handleStartDiscussion,
  }

  const heroBindings = computed(() => ({
    title: heroTitleText.value,
    pill: heroPillText.value,
    description: heroDescriptionText.value,
    variant: 'primary',
    filteredReadCount: filteredReadCount.value,
    filteredUnreadCount: filteredUnreadCount.value,
    marking: marking.value,
    markAllButtonText: markAllButtonText.value,
    clearReadButtonText: clearReadButtonText.value,
    unreadToggleText: unreadToggleText.value,
    preferencesLinkText: preferencesLinkText.value,
  }))

  const heroEvents = {
    clearReadNotifications: clearReadNotifications,
    markAllAsRead,
    toggleUnreadOnly,
  }

  const filterCardBindings = computed(() => ({
    activeNotificationLabel: activeNotificationLabel.value,
    activeType: activeType.value,
    filterDescriptionText: filterDescriptionText.value,
    notificationTypeItems: notificationTypeItems.value,
    viewMode: viewMode.value,
    viewModeItems: viewModeItems.value,
  }))

  const filterCardEvents = {
    changeType,
    changeViewMode,
  }

  const listBindings = computed(() => ({
    currentPage: currentPage.value,
    emptyStateText: emptyStateText.value,
    groupedNotifications: groupedNotifications.value,
    loadError: loadError.value,
    loading: loading.value,
    loadingStateText: loadingStateText.value,
    notifications: notifications.value,
    totalPages: totalPages.value,
    viewMode: viewMode.value,
    markGroupReadText: markGroupReadText.value,
    clearGroupReadText: clearGroupReadText.value,
    openDiscussionText: openDiscussionText.value,
    marking: marking.value,
    formatDate,
    getNotificationAvatarColor,
    getNotificationAvatarInitial,
    getNotificationIconClass,
    getNotificationMessageHtml,
    getNotificationPresentation,
    getUserDisplayName,
    groupCountText,
  }))

  const listEvents = {
    changePage,
    clearGroupReadNotifications,
    deleteNotification,
    handleNotificationClick,
    markAsRead,
    markGroupAsRead,
    openDiscussion(discussionId) {
      if (!discussionId) return
      router.push(`/d/${discussionId}`)
    },
  }

  return {
    filterCardBindings,
    filterCardEvents,
    heroBindings,
    heroEvents,
    listBindings,
    listEvents,
    sidebarBindings,
    sidebarEvents,
  }
}

export function useNotificationViewBindings(options) {
  return createNotificationViewBindings(options)
}
