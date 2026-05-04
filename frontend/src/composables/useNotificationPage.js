import { computed, onMounted, ref, watch } from 'vue'
import { getRegisteredNotificationTypes } from '@/forum/notificationTypes'
import { resolveNotificationPath, useNotificationGroups } from '@/composables/useNotificationPresentation'

export function useNotificationPage({
  modalStore,
  notificationStore,
  route,
  router
}) {
  const loading = ref(true)
  const loadError = ref('')
  const marking = ref(false)
  const currentPage = ref(1)
  const totalPages = ref(1)
  const activeType = ref('')
  const unreadOnly = ref(false)
  const viewMode = ref('timeline')
  const totalCount = ref(0)
  const notifications = computed(() => notificationStore.notifications)
  const groupedNotifications = useNotificationGroups(notifications, '论坛')
  const filteredUnreadCount = computed(() => notifications.value.filter(item => !item.is_read).length)
  const filteredReadCount = computed(() => notifications.value.length - filteredUnreadCount.value)
  const hasActiveFilter = computed(() => unreadOnly.value || Boolean(activeType.value))

  const notificationTypeItems = computed(() => {
    const registeredItems = getRegisteredNotificationTypes().map(item => ({
      value: item.type,
      label: item.label,
      count: formatTypeCount(item.type),
    }))

    return [
      { value: '', label: '全部通知', count: formatSummaryCount() },
      ...registeredItems,
    ]
  })

  const viewModeItems = computed(() => {
    return [
      { value: 'timeline', label: '时间流' },
      { value: 'grouped', label: '按讨论分组' },
    ]
  })

  function formatSummaryCount() {
    if (unreadOnly.value) {
      return `${notifications.value.length || 0} 未读`
    }
    return String(totalCount.value || notifications.value.length || 0)
  }

  function formatTypeCount(type) {
    const total = Number(notificationStore.typeCounts?.[type] || 0)
    const unread = Number(notificationStore.unreadTypeCounts?.[type] || 0)

    if (unread > 0) {
      return `${total} / ${unread} 未读`
    }

    return String(total)
  }

  onMounted(async () => {
    syncStateFromRoute()
    await loadNotifications()
  })

  watch(
    () => route.query.type,
    async () => {
      const nextType = normalizeTypeFilter(route.query.type)
      if (nextType === activeType.value) {
        return
      }
      activeType.value = nextType
      currentPage.value = 1
      await loadNotifications()
    }
  )

  watch(
    () => route.query.page,
    async () => {
      const nextPage = normalizePage(route.query.page)
      if (nextPage === currentPage.value) {
        return
      }
      currentPage.value = nextPage
      await loadNotifications()
    }
  )

  watch(
    () => route.query.state,
    async () => {
      const nextUnreadOnly = String(route.query.state || '').trim() === 'unread'
      if (nextUnreadOnly === unreadOnly.value) {
        return
      }
      unreadOnly.value = nextUnreadOnly
      currentPage.value = 1
      await loadNotifications()
    }
  )

  watch(
    () => route.query.view,
    async () => {
      const nextViewMode = String(route.query.view || '').trim() === 'grouped' ? 'grouped' : 'timeline'
      if (nextViewMode === viewMode.value) {
        return
      }
      viewMode.value = nextViewMode
    }
  )

  async function loadNotifications() {
    loading.value = true
    loadError.value = ''

    try {
      const data = await notificationStore.fetchNotifications({
        page: currentPage.value,
        ...(activeType.value ? { type: activeType.value } : {}),
        ...(unreadOnly.value ? { is_read: false } : {})
      })
      totalCount.value = Number(data.total || notifications.value.length || 0)
      totalPages.value = Math.max(1, Math.ceil((data.total || notifications.value.length) / (data.limit || 20)))
    } catch (error) {
      console.error('加载通知失败:', error)
      loadError.value = error.response?.data?.error || error.message || '加载通知失败，请稍后重试'
      totalCount.value = 0
      notificationStore.typeCounts = {}
      notificationStore.unreadTypeCounts = {}
    } finally {
      loading.value = false
    }
  }

  function normalizeTypeFilter(value) {
    return typeof value === 'string' ? value.trim() : ''
  }

  function normalizePage(value) {
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
  }

  function syncStateFromRoute() {
    activeType.value = normalizeTypeFilter(route.query.type)
    currentPage.value = normalizePage(route.query.page)
    unreadOnly.value = String(route.query.state || '').trim() === 'unread'
    viewMode.value = String(route.query.view || '').trim() === 'grouped' ? 'grouped' : 'timeline'
  }

  function buildQueryState({ type, page }) {
    const query = {}
    if (type) {
      query.type = type
    }
    if (unreadOnly.value) {
      query.state = 'unread'
    }
    if (viewMode.value === 'grouped') {
      query.view = 'grouped'
    }
    if (page > 1) {
      query.page = String(page)
    }
    return query
  }

  async function changeType(type) {
    const nextType = normalizeTypeFilter(type)
    if (nextType === activeType.value) {
      return
    }

    activeType.value = nextType
    currentPage.value = 1
    await router.push({
      name: 'notifications',
      query: buildQueryState({
        type: nextType,
        page: 1,
      })
    })
    await loadNotifications()
  }

  async function toggleUnreadOnly() {
    unreadOnly.value = !unreadOnly.value
    currentPage.value = 1
    await router.push({
      name: 'notifications',
      query: buildQueryState({
        type: activeType.value,
        page: 1,
      })
    })
    await loadNotifications()
  }

  async function changeViewMode(mode) {
    const nextMode = mode === 'grouped' ? 'grouped' : 'timeline'
    if (nextMode === viewMode.value) {
      return
    }
    viewMode.value = nextMode
    currentPage.value = 1
    await router.push({
      name: 'notifications',
      query: buildQueryState({
        type: activeType.value,
        page: 1,
      })
    })
  }

  async function markAsRead(notificationId) {
    try {
      await notificationStore.markAsRead(notificationId)
      const notification = notifications.value.find(item => item.id === notificationId)
      if (notification) {
        notification.is_read = true
      }
    } catch (error) {
      console.error('标记失败:', error)
    }
  }

  async function markAllAsRead() {
    const unreadCount = filteredUnreadCount.value
    if (unreadCount === 0) return

    const confirmed = await modalStore.confirm({
      title: hasActiveFilter.value ? '标记当前筛选结果为已读' : '全部标记为已读',
      message: hasActiveFilter.value
        ? `确定将当前筛选结果中的 ${unreadCount} 条未读通知标记为已读吗？`
        : `确定将当前 ${unreadCount} 条未读通知标记为已读吗？`,
      confirmText: '标记已读',
      cancelText: '取消',
      tone: 'primary'
    })
    if (!confirmed) return

    marking.value = true

    try {
      if (hasActiveFilter.value) {
        await notificationStore.markFilteredAsRead({
          type: activeType.value,
        })
      } else {
        await notificationStore.markAllAsRead()
      }
      await loadNotifications()
      await modalStore.alert({
        title: '已全部标记为已读',
        message: hasActiveFilter.value ? '当前筛选范围内的未读通知已更新为已读。' : '当前页面的未读通知已更新为已读。',
        tone: 'success'
      })
    } catch (error) {
      console.error('标记失败:', error)
      await modalStore.alert({
        title: '操作失败',
        message: error.response?.data?.error || error.message || '请稍后重试',
        tone: 'danger'
      })
    } finally {
      marking.value = false
    }
  }

  async function clearReadNotifications() {
    const readCount = filteredReadCount.value
    if (readCount === 0) return

    const confirmed = await modalStore.confirm({
      title: hasActiveFilter.value ? '清除当前筛选中的已读通知' : '清除当前页已读通知',
      message: hasActiveFilter.value
        ? `确定清除当前筛选结果中的 ${readCount} 条已读通知吗？`
        : `确定清除当前页中的 ${readCount} 条已读通知吗？`,
      confirmText: '清除已读',
      cancelText: '取消',
      tone: 'danger'
    })
    if (!confirmed) return

    marking.value = true

    try {
      if (hasActiveFilter.value) {
        await notificationStore.clearFilteredReadNotifications({
          type: activeType.value,
        })
      } else {
        await notificationStore.clearReadNotifications()
      }
      await loadNotifications()
      await modalStore.alert({
        title: '已清除已读通知',
        message: '当前范围内的已读通知已清除。',
        tone: 'success'
      })
    } catch (error) {
      console.error('清除失败:', error)
      await modalStore.alert({
        title: '操作失败',
        message: error.response?.data?.error || error.message || '请稍后重试',
        tone: 'danger'
      })
    } finally {
      marking.value = false
    }
  }

  async function markGroupAsRead(group) {
    const discussionId = Number(group?.discussionId || 0)
    const unreadCount = Array.isArray(group?.items) ? group.items.filter(item => !item.is_read).length : 0
    if (!discussionId || unreadCount === 0) return

    const confirmed = await modalStore.confirm({
      title: '标记该讨论通知为已读',
      message: `确定将“${group.title}”下的 ${unreadCount} 条未读通知标记为已读吗？`,
      confirmText: '标记已读',
      cancelText: '取消',
      tone: 'primary'
    })
    if (!confirmed) return

    marking.value = true
    try {
      await notificationStore.markFilteredAsRead({
        type: activeType.value,
        discussionId,
      })
      await loadNotifications()
    } catch (error) {
      console.error('分组标记失败:', error)
      await modalStore.alert({
        title: '操作失败',
        message: error.response?.data?.error || error.message || '请稍后重试',
        tone: 'danger'
      })
    } finally {
      marking.value = false
    }
  }

  async function clearGroupReadNotifications(group) {
    const discussionId = Number(group?.discussionId || 0)
    const readCount = Array.isArray(group?.items) ? group.items.filter(item => item.is_read).length : 0
    if (!discussionId || readCount === 0) return

    const confirmed = await modalStore.confirm({
      title: '清除该讨论中的已读通知',
      message: `确定清除“${group.title}”下的 ${readCount} 条已读通知吗？`,
      confirmText: '清除已读',
      cancelText: '取消',
      tone: 'danger'
    })
    if (!confirmed) return

    marking.value = true
    try {
      await notificationStore.clearFilteredReadNotifications({
        type: activeType.value,
        discussionId,
      })
      await loadNotifications()
    } catch (error) {
      console.error('分组清除失败:', error)
      await modalStore.alert({
        title: '操作失败',
        message: error.response?.data?.error || error.message || '请稍后重试',
        tone: 'danger'
      })
    } finally {
      marking.value = false
    }
  }

  async function deleteNotification(notificationId) {
    const confirmed = await modalStore.confirm({
      title: '删除通知',
      message: '确定要删除这条通知吗？',
      confirmText: '删除',
      cancelText: '取消',
      tone: 'danger'
    })
    if (!confirmed) return

    try {
      await notificationStore.deleteNotification(notificationId)
    } catch (error) {
      console.error('删除失败:', error)
      await modalStore.alert({
        title: '删除失败',
        message: error.response?.data?.error || error.message || '请稍后重试',
        tone: 'danger'
      })
    }
  }

  async function handleNotificationClick(notification) {
    if (!notification.is_read) {
      markAsRead(notification.id)
    }

    router.push(await resolveNotificationPath(notification))
  }

  async function changePage(page) {
    currentPage.value = page
    await router.push({
      name: 'notifications',
      query: buildQueryState({
        type: activeType.value,
        page,
      })
    })
    await loadNotifications()

    if (typeof window !== 'undefined') {
      window.scrollTo(0, 0)
    }
  }

  return {
    notifications,
    loading,
    loadError,
    marking,
    currentPage,
    totalPages,
    activeType,
    unreadOnly,
    viewMode,
    filteredUnreadCount,
    filteredReadCount,
    hasActiveFilter,
    notificationTypeItems,
    viewModeItems,
    groupedNotifications,
    markAsRead,
    markAllAsRead,
    clearReadNotifications,
    markGroupAsRead,
    clearGroupReadNotifications,
    deleteNotification,
    handleNotificationClick,
    changeType,
    changeViewMode,
    toggleUnreadOnly,
    changePage
  }
}
