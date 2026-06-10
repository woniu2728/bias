import test from 'node:test'
import assert from 'node:assert/strict'
import { useDiscussionListPageActions } from './useDiscussionListPageActions.js'

test('discussion list page actions pass extension state and route name to start discussion', () => {
  const calls = []
  const actions = useDiscussionListPageActions({
    discussionListContextData: {
      value: {
        tags: {
          startDiscussionExtensionState: {
            tags: {
              requestedTagId: '42',
            },
          },
        },
      },
    },
    route: {
      name: 'following',
    },
    startDiscussion(payload) {
      calls.push(payload)
      return true
    },
  })

  const result = actions.handleStartDiscussion()

  assert.equal(result, true)
  assert.deepEqual(calls, [{
    extensionState: {
      tags: {
        requestedTagId: '42',
      },
    },
    source: 'following',
  }])
})

test('discussion list page actions fall back to index source when route name is absent', () => {
  const calls = []
  const actions = useDiscussionListPageActions({
    discussionListContextData: { value: {} },
    route: {
      name: null,
    },
    startDiscussion(payload) {
      calls.push(payload)
      return false
    },
  })

  const result = actions.handleStartDiscussion()

  assert.equal(result, false)
  assert.deepEqual(calls, [{
    extensionState: {},
    source: 'index',
  }])
})
