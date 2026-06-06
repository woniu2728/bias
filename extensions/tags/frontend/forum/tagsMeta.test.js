import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveTagsMetaPayload } from './tagsMeta.js'

test('tags meta helper includes canonical url and count-aware defaults', () => {
  assert.deepEqual(resolveTagsMetaPayload({
    tagCount: 12,
    titleText: '',
    descriptionText: '',
  }), {
    title: '全部标签',
    description: '浏览 12 个论坛标签，按主题发现相关讨论。',
    canonicalUrl: '/tags',
  })
})

test('tags meta helper prefers provided title and description copy', () => {
  assert.deepEqual(resolveTagsMetaPayload({
    tagCount: 0,
    titleText: '标签广场',
    descriptionText: '探索社区主题地图。',
  }), {
    title: '标签广场',
    description: '探索社区主题地图。',
    canonicalUrl: '/tags',
  })
})
