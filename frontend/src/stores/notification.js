import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const ws = ref(null)
  let heartbeatTimer = null
  let reconnectTimer = null

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
    if (!token) return

    if (ws.value && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.value.readyState)) {
      return
    }

    const baseUrl = resolveWsBaseUrl()
    ws.value = new WebSocket(`${baseUrl}/ws/notifications/?token=${encodeURIComponent(token)}`)

    ws.value.onopen = () => {
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

        // 显示浏览器通知
        if (Notification.permission === 'granted') {
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

  // 标记为已读
  function markAsRead(notificationId) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({
        type: 'mark_read',
        notification_id: notificationId
      }))
    }

    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification && !notification.is_read) {
      notification.is_read = true
      unreadCount.value--
    }
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
    connect,
    disconnect,
    markAsRead,
    requestPermission
  }
})
