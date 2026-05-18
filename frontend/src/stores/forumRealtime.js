import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useResourceStore } from '@/stores/resource'

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

export const useForumRealtimeStore = defineStore('forumRealtime', () => {
  const resourceStore = useResourceStore()
  const connectionState = ref('idle')
  const connectionFailureCount = ref(0)
  let ws = null
  let heartbeatTimer = null
  let reconnectTimer = null
  let shouldReconnect = false
  let connectFailures = 0
  const subscribedDiscussionIds = new Set()
  const pendingDiscussionIds = new Set()
  const trackedDiscussionCounts = new Map()
  const isConnected = computed(() => connectionState.value === 'connected')
  const isReconnecting = computed(() => connectionState.value === 'reconnecting')
  const hasConnectionError = computed(() => connectionState.value === 'error')

  function setConnectionState(nextState) {
    connectionState.value = nextState
  }

  function connect() {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return
    if (ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.readyState)) return

    shouldReconnect = true
    setConnectionState(connectFailures > 0 ? 'reconnecting' : 'connecting')
    const socket = new WebSocket(`${resolveWsBaseUrl()}/ws/forum/`)
    ws = socket
    let didOpen = false

    socket.onopen = () => {
      didOpen = true
      connectFailures = 0
      connectionFailureCount.value = 0
      setConnectionState('connected')
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
      flushSubscriptions()
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'forum_event') {
          applyForumEvent(data.event)
        }
        if (data.type === 'subscribed') {
          applySubscribedIds(data.discussion_ids)
        }
        if (data.type === 'unsubscribed') {
          applyUnsubscribedIds(data.discussion_ids)
        }
      } catch (error) {
        console.error('解析论坛实时消息失败:', error)
      }
    }

    socket.onclose = () => {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
        heartbeatTimer = null
      }

      subscribedDiscussionIds.clear()
      if (!shouldReconnect) {
        setConnectionState('idle')
        return
      }

      if (!didOpen) {
        connectFailures += 1
        connectionFailureCount.value = connectFailures
        if (connectFailures >= 2) {
          shouldReconnect = false
          setConnectionState('error')
          return
        }
      }

      setConnectionState('reconnecting')
      reconnectTimer = setTimeout(() => {
        connect()
      }, 5000)
    }
  }

  function disconnect() {
    shouldReconnect = false
    setConnectionState('idle')
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    subscribedDiscussionIds.clear()
    pendingDiscussionIds.clear()
    trackedDiscussionCounts.clear()
    if (ws) {
      ws.close()
      ws = null
    }
  }

  function trackDiscussionIds(ids = []) {
    let changed = false
    ids.forEach(rawId => {
      const discussionId = Number(rawId)
      if (!Number.isInteger(discussionId) || discussionId <= 0) return
      const nextCount = Number(trackedDiscussionCounts.get(discussionId) || 0) + 1
      trackedDiscussionCounts.set(discussionId, nextCount)
      if (nextCount === 1) {
        pendingDiscussionIds.add(discussionId)
        changed = true
      }
    })

    if (changed) {
      flushSubscriptions()
    }
  }

  function untrackDiscussionIds(ids = []) {
    const discussionIds = ids
      .map(value => Number(value))
      .filter(value => Number.isInteger(value) && value > 0)

    const removableIds = []
    discussionIds.forEach(id => {
      pendingDiscussionIds.delete(id)
      const currentCount = Number(trackedDiscussionCounts.get(id) || 0)
      if (currentCount <= 1) {
        trackedDiscussionCounts.delete(id)
        removableIds.push(id)
        return
      }
      trackedDiscussionCounts.set(id, currentCount - 1)
    })

    if (ws?.readyState !== WebSocket.OPEN) {
      removableIds.forEach(id => subscribedDiscussionIds.delete(id))
      return
    }

    const subscribedRemovableIds = removableIds.filter(id => subscribedDiscussionIds.has(id))
    if (!subscribedRemovableIds.length) return
    ws.send(JSON.stringify({
      type: 'unsubscribe_discussions',
      discussion_ids: subscribedRemovableIds,
    }))
  }

  function flushSubscriptions() {
    if (!pendingDiscussionIds.size) return
    if (ws?.readyState !== WebSocket.OPEN) return

    const discussionIds = [...pendingDiscussionIds]
    pendingDiscussionIds.clear()
    ws.send(JSON.stringify({
      type: 'subscribe_discussions',
      discussion_ids: discussionIds,
    }))
  }

  function applySubscribedIds(ids = []) {
    ids.forEach(rawId => {
      const discussionId = Number(rawId)
      if (!Number.isInteger(discussionId) || discussionId <= 0) return
      subscribedDiscussionIds.add(discussionId)
    })
  }

  function applyUnsubscribedIds(ids = []) {
    ids.forEach(rawId => {
      const discussionId = Number(rawId)
      if (!Number.isInteger(discussionId) || discussionId <= 0) return
      subscribedDiscussionIds.delete(discussionId)
    })
  }

  function applyForumEvent(event) {
    if (!event) return

    const payload = event.payload || {}
    resourceStore.mergePayload(payload)

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('bias:forum-event', {
        detail: event,
      }))
    }
  }

  function resetState() {
    disconnect()
    connectFailures = 0
    connectionFailureCount.value = 0
  }

  return {
    connectionState,
    connectionFailureCount,
    hasConnectionError,
    isConnected,
    isReconnecting,
    connect,
    disconnect,
    resetState,
    trackDiscussionIds,
    untrackDiscussionIds,
  }
})
