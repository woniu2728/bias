import test from 'node:test'
import assert from 'node:assert/strict'
import { createNotificationDisplayState } from './useNotificationDisplayState.js'

function createHarness(overrides = {}) {
  return createNotificationDisplayState({
    activeType: () => overrides.activeType ?? 'mention',
    getNotificationUiCopy(_surface, _context, fallback = '') {
      return fallback
    },
    getTotalCount: () => overrides.totalCount ?? 12,
    getTypeCounts: () => overrides.typeCounts ?? { mention: 8, approval: 2 },
    getUnreadOnly: () => overrides.unreadOnly ?? false,
    getUnreadTypeCounts: () => overrides.unreadTypeCounts ?? { mention: 3, approval: 0 },
    loading: () => overrides.loading ?? false,
    notifications: () => overrides.notifications ?? [
      { id: 1, is_read: false },
      { id: 2, is_read: true },
    ],
  })
}

test('notification display state formats summary and type counts from totals and unread stats', () => {
  const state = createHarness()

  assert.equal(state.formatSummaryCount(), '12')
  assert.equal(state.formatTypeCount('mention'), '8 / 3 未读')
  assert.equal(state.formatTypeCount('approval'), '2')
})

test('notification display state builds filter and view mode items', () => {
  const state = createHarness({
    unreadOnly: true,
    notifications: [{ id: 1, is_read: false }],
  })

  assert.equal(state.emptyStateText.value, '暂无通知')
  assert.equal(state.loadingStateText.value, '正在加载通知...')
  assert.deepEqual(state.notificationTypeItems.value[0], {
    value: '',
    label: '全部通知',
    count: '1 未读',
  })
  assert.deepEqual(state.viewModeItems.value, [
    { value: 'timeline', label: '时间流' },
    { value: 'grouped', label: '按讨论分组' },
  ])
})
