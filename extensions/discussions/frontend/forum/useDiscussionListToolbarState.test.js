import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListToolbarState } from './useDiscussionListToolbarState.js'

test('discussion list toolbar state filters visible sort options and resolves copy', () => {
  const state = createDiscussionListToolbarState({
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
    markingAllRead: ref(true),
    refreshing: ref(true),
    sortOptions: ref([
      { code: 'latest', label: 'Latest' },
      { code: 'hidden', label: 'Hidden', toolbar_visible: false },
    ]),
  })

  assert.deepEqual(state.normalizedSortOptions.value, [{ code: 'latest', label: 'Latest' }])
  assert.equal(state.markAllReadTitleText.value, 'discussion-list-toolbar-mark-read-copy')
  assert.equal(state.refreshTitleText.value, 'discussion-list-toolbar-refresh-copy')
})

test('discussion list toolbar state falls back to default sort options', () => {
  const state = createDiscussionListToolbarState({
    getText: ({ code }) => code ? { text: `${code}-label` } : null,
    markingAllRead: ref(false),
    refreshing: ref(false),
    sortOptions: ref([]),
  })

  assert.deepEqual(state.normalizedSortOptions.value.map(item => item.code), ['latest', 'newest', 'top'])
  assert.equal(state.normalizedSortOptions.value[0].label, 'latest-label')
  assert.equal(state.markAllReadTitleText.value, '全部标记为已读')
  assert.equal(state.refreshTitleText.value, '刷新')
})
