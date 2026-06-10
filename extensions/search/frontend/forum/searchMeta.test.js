import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveSearchMetaPayload } from './searchMeta.js'

test('search meta helper includes encoded query and type in canonical url', () => {
  assert.deepEqual(resolveSearchMetaPayload({
    query: 'python tips',
    searchType: 'posts',
    titleText: '',
    descriptionText: '',
  }), {
    title: '搜索：python tips',
    description: '查看“python tips”相关的讨论、回复和用户结果。',
    canonicalUrl: '/search?q=python%20tips&type=posts',
  })
})

test('search meta helper falls back to base search page when query is empty', () => {
  assert.deepEqual(resolveSearchMetaPayload({
    query: '',
    searchType: 'all',
    titleText: '搜索首页',
    descriptionText: '浏览论坛搜索入口。',
  }), {
    title: '搜索首页',
    description: '浏览论坛搜索入口。',
    canonicalUrl: '/search',
  })
})
