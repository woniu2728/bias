import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import { unwrapList } from '@/utils/forum'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
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

    loading.value = true
    try {
      const data = await api.get('/notifications', {
        params: {
          page,
          limit
        }
      })
      notifications.value = unwrapList(data)
      unreadCount.value = Number(data.unread_count || 0)
      initialized.value = true
      return data
    } finally {
      loading.value = false
    }
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
    }
  }

  async function markAllAsRead() {
    await api.post('/notifications/read-all')
    notifications.value.forEach(notification => {
      notification.is_read = true
    })
    unreadCount.value = 0
  }

  async function deleteNotification(notificationId) {
    const notification = notifications.value.find(n => n.id === notificationId)
    await api.delete(`/notifications/${notificationId}`)
    notifications.value = notifications.value.filter(n => n.id !== notificationId)
    if (notification && !notification.is_read) {
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  }

  async function clearReadNotifications() {
    await api.delete('/notifications/read')
    notifications.value = notifications.value.filter(notification => !notification.is_read)
  }

  // 获取通知消息
  function getNotificationMessage(notification) {
    switch (notification.type) {
      case 'discussionReply':
        return '您的讨论有新回复'
      case 'postLiked':
        return '您的帖子被点赞'
      case 'userMentioned':
        return '有人@了您'
      case 'postReply':
        return '有人回复了您的帖子'
      default:
        return '您有新通知'
    }
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
    loading,
    initialized,
    connect,
    disconnect,
    fetchNotifications,
    ensureFetched,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearReadNotifications,
    getNotificationMessage,
    requestPermission
  }
})
