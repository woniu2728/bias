import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { useForumRealtimeStatus } from './useForumRealtimeStatus.js'

function getText(context = {}) {
  if (context.surface === 'forum-realtime-status-reconnecting') {
    return { text: '论坛实时连接已断开，正在尝试重新连接...' }
  }
  if (context.surface === 'forum-realtime-status-error') {
    return { text: '论坛实时连接暂时不可用，稍后会在下次页面交互时重试。' }
  }
  return null
}

test('forum realtime status hides banner for guests and healthy connections', () => {
  const status = useForumRealtimeStatus({
    authStore: { isAuthenticated: false },
    forumRealtimeStore: {
      isReconnecting: ref(false),
      hasConnectionError: ref(false),
      connectionFailureCount: ref(0),
    },
    getText,
  })

  assert.equal(status.shouldShow.value, false)
  assert.equal(status.text.value, '')
})

test('forum realtime status resolves reconnecting banner copy', () => {
  const status = useForumRealtimeStatus({
    authStore: { isAuthenticated: true },
    forumRealtimeStore: {
      isReconnecting: ref(true),
      hasConnectionError: ref(false),
      connectionFailureCount: ref(1),
    },
    getText,
  })

  assert.equal(status.shouldShow.value, true)
  assert.equal(status.tone.value, 'info')
  assert.equal(status.text.value, '论坛实时连接已断开，正在尝试重新连接...')
})

test('forum realtime status resolves terminal error banner copy', () => {
  const status = useForumRealtimeStatus({
    authStore: { isAuthenticated: true },
    forumRealtimeStore: {
      isReconnecting: ref(false),
      hasConnectionError: ref(true),
      connectionFailureCount: ref(2),
    },
    getText,
  })

  assert.equal(status.shouldShow.value, true)
  assert.equal(status.tone.value, 'warning')
  assert.equal(status.text.value, '论坛实时连接暂时不可用，稍后会在下次页面交互时重试。')
})
