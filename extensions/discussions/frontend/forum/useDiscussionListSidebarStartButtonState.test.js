import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListSidebarStartButtonState } from './useDiscussionListSidebarStartButtonState.js'

test('discussion list sidebar start button state resolves registry copy', () => {
  const state = createDiscussionListSidebarStartButtonState({
    contextSubject: ref({ name: '公告' }),
    getText: ({ surface, subjectName }) => ({ text: `${surface}-${subjectName}-copy` }),
  })

  assert.equal(state.labelText.value, 'start-discussion-button-公告-copy')
})

test('discussion list sidebar start button state falls back to default label', () => {
  const state = createDiscussionListSidebarStartButtonState({
    contextSubject: ref(null),
    getText: () => null,
  })

  assert.equal(state.labelText.value, '发起讨论')
})
