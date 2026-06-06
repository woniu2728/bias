import test from 'node:test'
import assert from 'node:assert/strict'
import { createHeaderNotificationDisplayState } from './useHeaderNotificationDisplayState.js'

function createHarness(overrides = {}) {
  return createHeaderNotificationDisplayState({
    createNotificationGroups(notificationItems) {
      return {
        get value() {
          return [
            {
              key: 'group-1',
              title: '讨论一',
              discussionId: 7,
              items: notificationItems.value,
            },
          ]
        },
      }
    },
    getEmptyStateText(notificationItems) {
      return notificationItems.length ? '有通知' : '暂无通知'
    },
    getLoadingStateText(notificationItems) {
      return notificationItems.length ? '加载中（有通知）' : '加载中...'
    },
    getReadCount: () => overrides.readCount ?? 2,
    getResolvedTypes: () => overrides.resolvedTypes ?? [
      { type: 'mention', label: '提及' },
      { type: 'approval', label: '审核' },
      { type: 'reply', label: '回复' },
      { type: 'system', label: '系统' },
      { type: 'like', label: '点赞' },
    ],
    getTypeCounts: () => overrides.typeCounts ?? {
      mention: 4,
      approval: 1,
      reply: 0,
      system: 2,
      like: 1,
    },
    getUnreadTypeCounts: () => overrides.unreadTypeCounts ?? {
      mention: 2,
      approval: 0,
      reply: 0,
      system: 0,
      like: 1,
    },
    notifications: () => overrides.notifications ?? Array.from({ length: 10 }, (_, index) => ({
      id: index + 1,
      is_read: index % 2 === 0,
    })),
  })
}

test('header notification display state trims menu items and computes derived summaries', () => {
  const state = createHarness()

  assert.equal(state.notificationItems.value.length, 8)
  assert.equal(state.hasReadNotifications.value, true)
  assert.equal(state.emptyStateText.value, '有通知')
  assert.equal(state.loadingStateText.value, '加载中（有通知）')
  assert.deepEqual(state.notificationGroups.value, [
    {
      key: 'group-1',
      title: '讨论一',
      discussionId: 7,
      items: state.notificationItems.value,
    },
  ])
  assert.deepEqual(state.notificationTypeSummaries.value, [
    { type: 'mention', label: '提及', total: 4, unread: 2 },
    { type: 'approval', label: '审核', total: 1, unread: 0 },
    { type: 'system', label: '系统', total: 2, unread: 0 },
    { type: 'like', label: '点赞', total: 1, unread: 1 },
  ])
})

test('header notification display state falls back for empty menu and no read items', () => {
  const state = createHarness({
    notifications: [],
    readCount: 0,
    typeCounts: {},
    unreadTypeCounts: {},
  })

  assert.equal(state.hasReadNotifications.value, false)
  assert.equal(state.emptyStateText.value, '暂无通知')
  assert.equal(state.loadingStateText.value, '加载中...')
  assert.deepEqual(state.notificationTypeSummaries.value, [])
})
