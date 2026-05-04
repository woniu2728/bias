import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import { getNotificationText } from '@/composables/useNotificationPresentation'
import { useAuthStore } from '@/stores/auth'
import { unwrapList } from '@/utils/forum'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const readCount = ref(0)
  const totalCount = ref(0)
  const typeCounts = ref({})
  const unreadTypeCounts = ref({})
  const loading = ref(false)
  const initialized = ref(false)
  const ws = ref(null)
  const websocketDisabled = ref(false)
  let heartbeatTimer = null
  let reconnectTimer = null
  let consecutiveConnectFailures = 0

  function resolveWsBaseUrl() {
    const configured = import.meta.env.VITE_WS_BASE_URL?.trim()
    if (configured) {
      return configured.replace(/\/$/, '')
    }

    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${protocol}//${window.location.host}`
    }

    return 'ws://localhost:8000'
  }

  // 连接WebSocket
  function connect() {
    const token = localStorage.getItem('access_token')
    if (!token || websocketDisabled.value) return

    if (ws.value && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.value.readyState)) {
      return
    }

    const baseUrl = resolveWsBaseUrl()
    ws.value = new WebSocket(`${baseUrl}/ws/notifications/?token=${encodeURIComponent(token)}`)
    let didOpen = false

    ws.value.onopen = () => {
      didOpen = true
      consecutiveConnectFailures = 0
      console.log('WebSocket连接成功')

      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }

      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
      }

      // 发送心跳
      heartbeatTimer = setInterval(() => {
        if (ws.value?.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)
    }

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'notification') {
        // 收到新通知
        notifications.value.unshift(data.notification)
        unreadCount.value++
        initialized.value = true

        if (['userSuspended', 'userUnsuspended'].includes(data.notification?.type)) {
          const authStore = useAuthStore()
          authStore.fetchUser().catch(() => {})
        }

        // 显示浏览器通知
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('新通知', {
            body: getNotificationMessage(data.notification),
            icon: '/favicon.ico'
          })
        }
      }
    }

    ws.value.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }

    ws.value.onclose = () => {
      console.log('WebSocket连接关闭')

      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
        heartbeatTimer = null
      }

      if (!didOpen) {
        consecutiveConnectFailures += 1
        if (consecutiveConnectFailures >= 2) {
          websocketDisabled.value = true
          reconnectTimer = null
          console.warn('通知 WebSocket 不可用，已停止自动重连。')
          return
        }
      }

      // 5秒后重连
      reconnectTimer = setTimeout(() => {
        connect()
      }, 5000)
    }
  }

  // 断开连接
  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  async function fetchNotifications(params = {}) {
    const page = params.page || 1
    const limit = params.limit || 20
    const type = typeof params.type === 'string' ? params.type.trim() : ''
    const isRead = typeof params.is_read === 'boolean' ? params.is_read : null

    loading.value = true
    try {
      const data = await api.get('/notifications', {
        params: {
          page,
          limit,
          ...(type ? { type } : {}),
          ...(isRead === null ? {} : { is_read: isRead })
        }
      })
      notifications.value = unwrapList(data)
      totalCount.value = Number(data.total || notifications.value.length || 0)
      unreadCount.value = Number(data.unread_count || 0)
      readCount.value = Math.max(0, totalCount.value - unreadCount.value)
      typeCounts.value = { ...(data.type_counts || {}) }
      unreadTypeCounts.value = { ...(data.unread_type_counts || {}) }
      initialized.value = true
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    const data = await api.get('/notifications/stats')
    totalCount.value = Number(data.total || 0)
    unreadCount.value = Number(data.unread_count || 0)
    readCount.value = Number(data.read_count || Math.max(0, totalCount.value - unreadCount.value))
    return data
  }

  async function ensureFetched(params = {}) {
    if (initialized.value && notifications.value.length) {
      return notifications.value
    }

    await fetchNotifications(params)
    return notifications.value
  }

  async function markAsRead(notificationId) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({
        type: 'mark_read',
        notification_id: notificationId
      }))
    }

    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification?.is_read) {
      return
    }

    await api.post(`/notifications/${notificationId}/read`)

    if (notification && !notification.is_read) {
      notification.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
      readCount.value += 1
    }
  }

  async function markAllAsRead() {
    const data = await api.post('/notifications/read-all')
    notifications.value.forEach(notification => {
      notification.is_read = true
    })
    readCount.value += unreadCount.value
    unreadCount.value = 0
    return data
  }

  async function deleteNotification(notificationId) {
    const notification = notifications.value.find(n => n.id === notificationId)
    await api.delete(`/notifications/${notificationId}`)
    notifications.value = notifications.value.filter(n => n.id !== notificationId)
    totalCount.value = Math.max(0, totalCount.value - 1)
    if (notification && !notification.is_read) {
      unreadCount.value = Math.max(0, unreadCount.value - 1)
      return
    }
    readCount.value = Math.max(0, readCount.value - 1)
  }

  async function clearReadNotifications() {
    const data = await api.delete('/notifications/read/clear')
    notifications.value = notifications.value.filter(notification => !notification.is_read)
    const removedCount = Number(data.count || 0)
    totalCount.value = Math.max(0, totalCount.value - removedCount)
    readCount.value = Math.max(0, readCount.value - removedCount)
    return data
  }

  function resetState() {
    notifications.value = []
    unreadCount.value = 0
    readCount.value = 0
    totalCount.value = 0
    typeCounts.value = {}
    unreadTypeCounts.value = {}
    loading.value = false
    initialized.value = false
    websocketDisabled.value = false
    consecutiveConnectFailures = 0
  }

  // 获取通知消息
  function getNotificationMessage(notification) {
    return getNotificationText(notification, '您有新通知')
  }

  // 请求通知权限
  function requestPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }

  return {
    notifications,
    unreadCount,
    readCount,
    totalCount,
    typeCounts,
    unreadTypeCounts,
    loading,
    initialized,
    connect,
    disconnect,
    resetState,
    fetchNotifications,
    fetchStats,
    ensureFetched,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearReadNotifications,
    getNotificationMessage,
    requestPermission
  }
})
