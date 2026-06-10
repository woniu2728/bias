import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListSidebarState } from './useDiscussionListSidebarState.js'

test('discussion list sidebar state resolves visibility and copy', () => {
  const state = createDiscussionListSidebarState({
    authStore: ref({
      isAuthenticated: true,
      canStartDiscussion: true,
      isRestoringSession: false,
      user: { id: 7 },
    }),
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
  })

  assert.equal(state.showStartDiscussionButton.value, true)
  assert.equal(state.showProfileLink.value, true)
  assert.equal(state.profileLinkLabel.value, 'discussion-list-sidebar-profile-link-copy')
})

test('discussion list sidebar state hides start button while restoring missing user', () => {
  const state = createDiscussionListSidebarState({
    authStore: ref({
      isAuthenticated: true,
      canStartDiscussion: true,
      isRestoringSession: true,
      user: null,
    }),
    getText: () => null,
  })

  assert.equal(state.showStartDiscussionButton.value, false)
  assert.equal(state.showProfileLink.value, false)
  assert.equal(state.profileLinkLabel.value, '我的主页')
})
