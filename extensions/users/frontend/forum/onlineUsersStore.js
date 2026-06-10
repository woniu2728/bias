import { computed, defineStore, ref } from '@bias/core'

function resolveWsBaseUrl() {
  const configured = import.meta.env?.VITE_WS_BASE_URL?.trim()
  if (configured) {
    return configured.replace(/\/$/, '')
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}`
  }

  return 'ws://localhost:8000'
}

export const useOnlineUsersStore = defineStore('onlineUsers', () => {
  const onlineUserIds = ref([])
  const connectionState = ref('idle')
  let ws = null
  let heartbeatTimer = null
  let reconnectTimer = null
  let shouldReconnect = false

  const isConnected = computed(() => connectionState.value === 'connected')

  function connect() {
    if (ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.readyState)) return

    shouldReconnect = true
    connectionState.value = 'connecting'
    const socket = new WebSocket(`${resolveWsBaseUrl()}/ws/online/`)
    ws = socket

    socket.onopen = () => {
      connectionState.value = 'connected'
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
      }
      heartbeatTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'online_users') {
          onlineUserIds.value = Array.isArray(data.users)
            ? data.users.map(item => Number(item?.id)).filter(id => Number.isInteger(id) && id > 0)
            : []
        }
        if (data.type === 'user_status') {
          applyUserStatus(data.user_id, data.status)
        }
      } catch (error) {
        console.error('解析在线用户消息失败:', error)
      }
    }

    socket.onclose = () => {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
        heartbeatTimer = null
      }

      if (!shouldReconnect) {
        connectionState.value = 'idle'
        return
      }

      connectionState.value = 'reconnecting'
      reconnectTimer = setTimeout(() => {
        connect()
      }, 5000)
    }
  }

  function disconnect() {
    shouldReconnect = false
    connectionState.value = 'idle'
    onlineUserIds.value = []
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  function reconnect() {
    disconnect()
    connect()
  }

  function applyUserStatus(rawUserId, status) {
    const userId = Number(rawUserId)
    if (!Number.isInteger(userId) || userId <= 0) return

    const currentIds = new Set(onlineUserIds.value)
    if (status === 'online') {
      currentIds.add(userId)
    }
    if (status === 'offline') {
      currentIds.delete(userId)
    }
    onlineUserIds.value = [...currentIds]
  }

  function isUserOnline(userId) {
    const normalizedId = Number(userId)
    if (!Number.isInteger(normalizedId) || normalizedId <= 0) return false
    return onlineUserIds.value.includes(normalizedId)
  }

  return {
    connectionState,
    isConnected,
    onlineUserIds,
    applyUserStatus,
    connect,
    disconnect,
    isUserOnline,
    reconnect,
  }
})
