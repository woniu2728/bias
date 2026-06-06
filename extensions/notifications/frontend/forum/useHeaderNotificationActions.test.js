import test from 'node:test'
import assert from 'node:assert/strict'
import { createHeaderNotificationActions } from './useHeaderNotificationActions.js'

function createHarness(overrides = {}) {
  const calls = []
  const state = {
    actionMessage: overrides.actionMessage ?? 'old message',
    actionTone: overrides.actionTone ?? 'info',
    clearingRead: false,
    markingAllRead: false,
    showNotifications: overrides.showNotifications ?? false,
  }
  const notificationStore = {
    async fetchNotifications(payload) {
      calls.push(['fetchNotifications', payload])
      if (overrides.fetchNotificationsError) {
        throw overrides.fetchNotificationsError
      }
    },
    async markAllAsRead() {
      calls.push('markAllAsRead')
      if (overrides.markAllError) {
        throw overrides.markAllError
      }
      return overrides.markAllResult ?? { message: '全部已读' }
    },
    async clearReadNotifications() {
      calls.push('clearReadNotifications')
      if (overrides.clearReadError) {
        throw overrides.clearReadError
      }
      return overrides.clearReadResult ?? { message: '已清除已读' }
    },
    async markAsRead(id) {
      calls.push(['markAsRead', id])
      if (overrides.markAsReadError) {
        throw overrides.markAsReadError
      }
    },
  }
  const router = {
    push(path) {
      calls.push(['push', path])
    },
  }
  const modalStore = overrides.modalStore === undefined
    ? {
      async confirm(payload) {
        calls.push(['confirm', payload])
        return overrides.confirmResult ?? true
      },
    }
    : overrides.modalStore

  const actions = createHeaderNotificationActions({
    getNotificationErrorMessage(error, fallback) {
      return error?.message || fallback
    },
    getNotificationUiCopy(_surface, _context, fallback) {
      return fallback
    },
    hasReadNotifications() {
      return overrides.hasReadNotifications ?? true
    },
    modalStore,
    notificationStore,
    async resolvePath(notification) {
      calls.push(['resolvePath', notification.id])
      return `/notifications/${notification.id}`
    },
    router,
    setActionMessage(value) {
      state.actionMessage = value
      calls.push(['setActionMessage', value])
    },
    setActionTone(value) {
      state.actionTone = value
      calls.push(['setActionTone', value])
    },
    setClearingRead(value) {
      state.clearingRead = value
      calls.push(['setClearingRead', value])
    },
    setMarkingAllRead(value) {
      state.markingAllRead = value
      calls.push(['setMarkingAllRead', value])
    },
    setShowNotifications(value) {
      state.showNotifications = value
      calls.push(['setShowNotifications', value])
    },
    async showHeaderNotificationError(error) {
      calls.push(['showHeaderNotificationError', error.message])
    },
    showNotifications() {
      return state.showNotifications
    },
  })

  return {
    actions,
    calls,
    state,
  }
}

test('header notification actions open menu and refresh latest notifications', async () => {
  const harness = createHarness()

  await harness.actions.toggleNotifications()

  assert.equal(harness.state.showNotifications, true)
  assert.equal(harness.state.actionMessage, '')
  assert.deepEqual(harness.calls, [
    ['setShowNotifications', true],
    ['setActionMessage', ''],
    ['fetchNotifications', { limit: 8 }],
  ])
})

test('header notification actions mark all as read and refresh feedback state', async () => {
  const harness = createHarness()

  await harness.actions.markAllNotificationsAsRead()

  assert.equal(harness.state.markingAllRead, false)
  assert.equal(harness.state.actionTone, 'success')
  assert.equal(harness.state.actionMessage, '全部已读')
  assert.deepEqual(harness.calls, [
    ['setMarkingAllRead', true],
    'markAllAsRead',
    ['fetchNotifications', { limit: 8 }],
    ['setActionTone', 'success'],
    ['setActionMessage', '全部已读'],
    ['setMarkingAllRead', false],
  ])
})

test('header notification actions stop clear-read when there are no read notifications', async () => {
  const harness = createHarness({
    hasReadNotifications: false,
  })

  await harness.actions.clearReadNotifications()

  assert.deepEqual(harness.calls, [])
})

test('header notification actions confirm clear-read and surface failures', async () => {
  const harness = createHarness({
    clearReadError: new Error('clear failed'),
  })

  await harness.actions.clearReadNotifications()

  assert.equal(harness.state.clearingRead, false)
  assert.equal(harness.state.actionTone, 'danger')
  assert.equal(harness.state.actionMessage, 'clear failed')
  assert.deepEqual(harness.calls, [
    ['confirm', {
      title: '清除已读通知',
      message: '确定要清除所有已读通知吗？未读通知会保留。',
      confirmText: '清除',
      cancelText: '取消',
      tone: 'danger'
    }],
    ['setClearingRead', true],
    'clearReadNotifications',
    ['setActionTone', 'danger'],
    ['setActionMessage', 'clear failed'],
    ['showHeaderNotificationError', 'clear failed'],
    ['setClearingRead', false],
  ])
})

test('header notification actions mark unread items then navigate and close menu', async () => {
  const harness = createHarness({
    showNotifications: true,
  })

  await harness.actions.handleNotificationClick({
    id: 9,
    is_read: false,
  })

  assert.equal(harness.state.showNotifications, false)
  assert.deepEqual(harness.calls, [
    ['markAsRead', 9],
    ['setShowNotifications', false],
    ['resolvePath', 9],
    ['push', '/notifications/9'],
  ])
})

test('header notification actions can close and route to grouped destinations', async () => {
  const harness = createHarness({
    showNotifications: true,
  })

  harness.actions.openNotificationGroup({ discussionId: 12 })
  harness.actions.openNotificationsPageByType('mention')
  harness.actions.openNotificationsPage()
  harness.actions.closeNotifications()

  assert.deepEqual(harness.calls, [
    ['setShowNotifications', false],
    ['push', '/d/12'],
    ['setShowNotifications', false],
    ['push', '/notifications?type=mention'],
    ['setShowNotifications', false],
    ['push', '/notifications'],
    ['setShowNotifications', false],
  ])
})
