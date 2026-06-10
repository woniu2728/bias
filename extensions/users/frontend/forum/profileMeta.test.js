import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveProfileMetaPayload } from './profileMeta.js'

test('profile meta helper resolves title, canonical url and normalized bio description', () => {
  assert.deepEqual(resolveProfileMetaPayload({
    id: 7,
    username: 'alice',
    display_name: 'Alice',
    bio: ' 热爱 论坛 \n 与 自动化 ',
    discussion_count: 12,
    comment_count: 34,
  }), {
    title: 'Alice 的主页',
    description: '热爱 论坛 与 自动化',
    canonicalUrl: '/u/alice',
  })
})

test('profile meta helper falls back to activity summary when bio is empty', () => {
  assert.deepEqual(resolveProfileMetaPayload({
    id: 9,
    username: '',
    display_name: '',
    bio: '',
    discussion_count: 3,
    comment_count: 8,
  }), {
    title: '用户 9 的主页',
    description: '用户 9 在论坛发布了 3 个讨论和 8 条回复。',
    canonicalUrl: '/u/9',
  })
})
