import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { createProfileContentSectionState } from './useProfileContentSectionState.js'

test('profile content section state resolves discussion section copy and badges', () => {
  const state = createProfileContentSectionState({
    getFeedback: () => ({ text: 'feedback-note' }),
    getDiscussionBadges: () => [{ key: 'locked' }],
    getEmpty: () => ({ text: 'empty-copy' }),
    getState: () => ({ text: 'loading-copy' }),
    isOwnProfile: ref(true),
    items: ref([{ id: 1 }]),
    kind: 'discussion',
    loading: ref(true),
  })

  assert.equal(state.loadingStateText.value, 'loading-copy')
  assert.equal(state.emptyStateText.value, 'empty-copy')
  assert.deepEqual(state.getStateBadges({ id: 1 }), [{ key: 'locked' }])
  assert.equal(state.getFeedbackNoteText({ id: 1 }), 'feedback-note')
})

test('profile content section state resolves post section defaults', () => {
  const state = createProfileContentSectionState({
    getFeedback: () => null,
    getEmpty: () => null,
    getPostBadges: () => [{ key: 'pending' }],
    getState: () => null,
    isOwnProfile: ref(false),
    items: ref([]),
    kind: 'post',
    loading: ref(false),
  })

  assert.equal(state.loadingStateText.value, '加载中...')
  assert.equal(state.emptyStateText.value, '暂无回复')
  assert.deepEqual(state.getStateBadges({ id: 2 }), [{ key: 'pending' }])
  assert.equal(state.getFeedbackNoteText({ id: 2 }), '')
})
