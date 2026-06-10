import { nextTick, reactive, ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListMetaState } from './useDiscussionListMetaState.js'

test('discussion list meta state syncs search meta with tag context', async () => {
  const metaCalls = []
  const searchQuery = ref('维护')
  const route = reactive({
    fullPath: '/tags/announcements?q=%E7%BB%B4%E6%8A%A4',
  })
  const metaState = createDiscussionListMetaState({
    contextSubject: ref({ name: '公告', description: '站点公告' }),
    forumStore: {
      setPageMeta(payload) {
        metaCalls.push(payload)
      },
    },
    isFollowingPage: ref(false),
    listFilter: ref('all'),
    route,
    searchQuery,
  })

  assert.equal(metaState.pageMetaTitle.value, '公告 - 搜索“维护”')
  assert.equal(metaState.pageMetaDescription.value, '查看“公告”范围内与“维护”相关的讨论。')
  assert.deepEqual(metaCalls, [{
    title: '公告 - 搜索“维护”',
    description: '查看“公告”范围内与“维护”相关的讨论。',
    canonicalUrl: '/tags/announcements?q=%E7%BB%B4%E6%8A%A4',
  }])

  searchQuery.value = '修复'
  route.fullPath = '/tags/announcements?q=%E4%BF%AE%E5%A4%8D'

  await nextTick()

  assert.equal(metaState.pageMetaTitle.value, '公告 - 搜索“修复”')
  assert.deepEqual(metaCalls.at(-1), {
    title: '公告 - 搜索“修复”',
    description: '查看“公告”范围内与“修复”相关的讨论。',
    canonicalUrl: '/tags/announcements?q=%E4%BF%AE%E5%A4%8D',
  })
})
