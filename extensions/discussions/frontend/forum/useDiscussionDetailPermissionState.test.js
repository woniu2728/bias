import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { useDiscussionDetailPermissionState } from './useDiscussionDetailPermissionState.js'

function createState(overrides = {}) {
  return useDiscussionDetailPermissionState({
    authStore: overrides.authStore || {
      isAuthenticated: false,
      user: null,
    },
    discussion: overrides.discussion || ref(null),
  })
}

test('discussion detail permission state exposes edit and menu permissions', () => {
  const state = createState({
    authStore: {
      isAuthenticated: true,
      user: {
        id: 3,
        is_staff: false,
        is_suspended: false,
      },
    },
    discussion: ref({
      can_edit: true,
      can_reply: true,
      is_locked: false,
    }),
  })

  assert.equal(state.canEditDiscussion.value, true)
  assert.equal(state.canReplyFromMenu.value, true)
  assert.equal(state.canShowDiscussionMenu.value, true)
})

test('discussion detail permission state builds suspension notice and blocks post actions', () => {
  const state = createState({
    authStore: {
      isAuthenticated: true,
      user: {
        id: 5,
        is_staff: false,
        is_suspended: true,
        suspended_until: '2026-05-20T10:00:00Z',
      },
    },
    discussion: ref({
      can_edit: true,
      can_reply: true,
      is_locked: false,
    }),
  })

  assert.equal(state.isSuspended.value, true)
  assert.match(state.suspensionNotice.value, /账号已被封禁至/)
  assert.equal(state.canEditPost({ user: { id: 5 } }), false)
})
