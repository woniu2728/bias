import test from 'node:test'
import assert from 'node:assert/strict'
import { createNotificationBulkActions } from './useNotificationBulkActions.js'

function createHarness(overrides = {}) {
  const calls = []
  const listState = {
    async refresh(payload) {
      calls.push(['refresh', payload])
    },
  }
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
    async markAllAsRead() {
      calls.push('markAllAsRead')
    },
    async markFilteredAsRead(payload) {
      calls.push(['markFilteredAsRead', payload])
    },
    async clearReadNotifications() {
      calls.push('clearReadNotifications')
    },
    async clearFilteredReadNotifications(payload) {
      calls.push(['clearFilteredReadNotifications', payload])
    },
  }

  const busyStates = []
  const actions = createNotificationBulkActions({
    activeType: () => overrides.activeType ?? 'mention',
    filteredReadCount: () => overrides.filteredReadCount ?? 4,
    filteredUnreadCount: () => overrides.filteredUnreadCount ?? 3,
    getNotificationUiCopy(_surface, _context, fallback = '') {
      return fallback
    },
    hasActiveFilter: () => overrides.hasActiveFilter ?? false,
    listState,
    modalStore,
    notificationStore,
    setBusy(value) {
      busyStates.push(value)
    },
    async showNotificationActionError(error) {
      calls.push(['showNotificationActionError', error.message])
    },
  })

  return {
    actions,
    busyStates,
    calls,
  }
}

test('notification bulk actions marks all notifications read without filter', async () => {
  const harness = createHarness({
    hasActiveFilter: false,
    activeType: '',
  })

  await harness.actions.markAllAsRead()

  assert.equal(harness.calls.some(item => item === 'markAllAsRead'), true)
  assert.deepEqual(harness.busyStates, [true, false])
})

test('notification bulk actions marks filtered notifications read when active filter exists', async () => {
  const harness = createHarness({
    hasActiveFilter: true,
    activeType: 'approval',
  })

  await harness.actions.markAllAsRead()

  assert.deepEqual(harness.calls.find(item => Array.isArray(item) && item[0] === 'markFilteredAsRead'), [
    'markFilteredAsRead',
    { type: 'approval' },
  ])
})

test('notification bulk actions clears grouped read notifications by discussion id', async () => {
  const harness = createHarness()

  await harness.actions.clearGroupReadNotifications({
    discussionId: 12,
    title: '讨论 A',
    items: [
      { is_read: true },
      { is_read: false },
      { is_read: true },
    ],
  })

  assert.deepEqual(harness.calls.find(item => Array.isArray(item) && item[0] === 'clearFilteredReadNotifications'), [
    'clearFilteredReadNotifications',
    { type: 'mention', discussionId: 12 },
  ])
})
