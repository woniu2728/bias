import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveDiscussionDetailMetaPayload } from './discussionDetailMeta.js'

test('discussion detail meta helper normalizes first post text into page meta payload', () => {
  assert.deepEqual(resolveDiscussionDetailMetaPayload({
    id: 12,
    title: '讨论标题',
    excerpt: '摘要',
    first_post: {
      content: ' 第一段内容\n第二段内容 ',
    },
  }), {
    title: '讨论标题',
    description: '第一段内容 第二段内容',
    ogType: 'article',
    canonicalUrl: '/d/12',
  })
})
