import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from '@bias/forum'
import { createTagsViewBindings } from './useTagsViewBindings.js'

test('tags view bindings expose sidebar, hero and content props', () => {
  const bindings = createTagsViewBindings({
    authStore: { isAuthenticated: true },
    cloudTags: ref([{ id: 2 }]),
    emptyStateText: ref('暂无标签'),
    handleStartDiscussion() {},
    heroDescriptionText: ref('浏览论坛标签'),
    heroTitleText: ref('全部标签'),
    loading: ref(false),
    loadingStateText: ref('加载中...'),
    showStartDiscussionButton: ref(true),
    tags: ref([{ id: 1 }]),
  })

  assert.deepEqual(bindings.sidebarBindings.value, {
    authStore: { isAuthenticated: true },
    showStartDiscussionButton: true,
  })
  assert.deepEqual(bindings.heroBindings.value, {
    title: '全部标签',
    description: '浏览论坛标签',
    variant: 'default',
  })
  assert.deepEqual(bindings.contentBindings.value, {
    cloudTags: [{ id: 2 }],
    emptyStateText: '暂无标签',
    loading: false,
    loadingStateText: '加载中...',
    tags: [{ id: 1 }],
  })
})

test('tags view bindings expose stable sidebar event handlers', () => {
  const calls = []
  const bindings = createTagsViewBindings({
    authStore: { isAuthenticated: false },
    cloudTags: ref([]),
    emptyStateText: ref('暂无标签'),
    handleStartDiscussion() {
      calls.push('start')
    },
    heroDescriptionText: ref('浏览论坛标签'),
    heroTitleText: ref('全部标签'),
    loading: ref(true),
    loadingStateText: ref('加载中...'),
    showStartDiscussionButton: ref(false),
    tags: ref([]),
  })

  bindings.sidebarEvents.startDiscussion()

  assert.deepEqual(calls, ['start'])
})
