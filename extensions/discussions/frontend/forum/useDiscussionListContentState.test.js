import test from 'node:test'
import assert from 'node:assert/strict'
import { createDiscussionListContentState } from './useDiscussionListContentState.js'

test('discussion list content state resolves registry copy', () => {
  const state = createDiscussionListContentState({
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
  })

  assert.equal(state.refreshingText.value, 'discussion-list-refreshing-copy')
  assert.equal(state.loadMoreText.value, 'discussion-list-load-more-copy')
  assert.equal(state.loadingMoreText.value, 'discussion-list-loading-more-copy')
})

test('discussion list content state falls back to defaults', () => {
  const state = createDiscussionListContentState({
    getText: () => null,
  })

  assert.equal(state.refreshingText.value, '正在刷新讨论')
  assert.equal(state.loadMoreText.value, '加载更多讨论')
  assert.equal(state.loadingMoreText.value, '正在加载讨论...')
})
