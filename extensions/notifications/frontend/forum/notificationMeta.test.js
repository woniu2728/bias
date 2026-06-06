import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveNotificationMetaPayload } from './notificationMeta.js'

test('notification meta helper preserves active filters in canonical url', () => {
  assert.deepEqual(resolveNotificationMetaPayload({
    activeLabel: '提及',
    activeType: 'mention',
    currentPage: 3,
    unreadOnly: true,
    viewMode: 'grouped',
  }), {
    title: '提及未读通知',
    description: '查看论坛中的未读回复提醒、提及、点赞、审核和系统通知。',
    canonicalUrl: '/notifications?type=mention&page=3&state=unread&view=grouped',
  })
})

test('notification meta helper omits default route state from canonical url', () => {
  assert.deepEqual(resolveNotificationMetaPayload({
    activeLabel: '',
    activeType: '',
    currentPage: 1,
    unreadOnly: false,
    viewMode: 'timeline',
  }), {
    title: '通知',
    description: '查看论坛中的回复提醒、提及、点赞、审核和系统通知。',
    canonicalUrl: '/notifications',
  })
})
