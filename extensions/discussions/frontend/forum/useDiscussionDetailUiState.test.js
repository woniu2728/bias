import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { useDiscussionDetailUiState } from './useDiscussionDetailUiState.js'

function createState(overrides = {}) {
  return useDiscussionDetailUiState({
    authStore: overrides.authStore || {
      isAuthenticated: false,
      user: null,
    },
    composerStore: overrides.composerStore || {
      current: {
        type: '',
        discussionId: null,
      },
    },
    currentVisiblePostProgress: overrides.currentVisiblePostProgress || ref(1),
    discussion: overrides.discussion || ref(null),
    isSuspended: overrides.isSuspended || ref(false),
    maxPostNumber: overrides.maxPostNumber || ref(10),
  })
}

test('discussion detail ui state detects active composer for the current discussion', () => {
  const state = createState({
    composerStore: {
      current: {
        type: 'reply',
        discussionId: 42,
      },
    },
    discussion: ref({ id: 42 }),
  })

  assert.equal(state.hasActiveComposer.value, true)
})

test('discussion detail ui state toggles discussion and post menus independently', () => {
  const state = createState({
    discussion: ref({ id: 7, can_reply: true }),
  })

  state.toggleDiscussionMenu()
  assert.equal(state.showDiscussionMenu.value, true)

  state.togglePostMenu(11)
  assert.equal(state.activePostMenuId.value, 11)

  state.togglePostMenu(11)
  assert.equal(state.activePostMenuId.value, null)

  state.resetTransientUiState()
  assert.equal(state.showDiscussionMenu.value, false)
  assert.equal(state.activePostMenuId.value, null)
})
