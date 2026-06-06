import test from 'node:test'
import assert from 'node:assert/strict'
import { createNotificationItemActions } from './useNotificationItemActions.js'

function createHarness(overrides = {}) {
  const calls = []
  const notificationItems = overrides.notificationItems || [
    { id: 1, is_read: false, path: '/d/1' },
  ]
  const modalStore = {
    async confirm(payload) {
      calls.push(['confirm', payload])
      return overrides.confirmResult ?? true
    },
    async alert(payload) {
      calls.push(['alert', payload])
    },
  }
  const notificationStore = {
    async markAsRead(notificationId) {
      calls.push(['markAsRead', notificationId])
    },
    async deleteNotification(notificationId) {
      calls.push(['deleteNotification', notificationId])
    },
  }
  const router = {
    push(path) {
      calls.push(['router.push', path])
    },
  }

  const actions = createNotificationItemActions({
    getNotificationErrorMessage(error) {
      return error.message
    },
    getNotificationUiCopy(_surface, _context, fallback = '') {
      return fallback
    },
    modalStore,
    notificationStore,
    notifications: () => notificationItems,
    async resolvePath(notification) {
      return notification.path
    },
    router,
  })

  return {
    actions,
    calls,
    notificationItems,
  }
}

test('notification item actions marks unread notification before navigation', async () => {
  const harness = createHarness({
    notificationItems: [{ id: 7, is_read: false, path: '/d/7' }],
  })

  await harness.actions.handleNotificationClick(harness.notificationItems[0])

  assert.deepEqual(harness.calls.slice(0, 2), [
    ['markAsRead', 7],
    ['router.push', '/d/7'],
  ])
  assert.equal(harness.notificationItems[0].is_read, true)
})

test('notification item actions confirms before deleting notification', async () => {
  const harness = createHarness()

  await harness.actions.deleteNotification(1)

  assert.equal(harness.calls.some(item => Array.isArray(item) && item[0] === 'confirm'), true)
  assert.equal(harness.calls.some(item => Array.isArray(item) && item[0] === 'deleteNotification'), true)
})
