import test from 'node:test'
import assert from 'node:assert/strict'
import { createDiscussionListRealtimeLifecycleState } from './useDiscussionListRealtimeLifecycleState.js'

function createLifecycleHarness() {
  const calls = []
  const lifecycle = createDiscussionListRealtimeLifecycleState({
    addWindowEventListener(type, handler) {
      calls.push(['add-window-event-listener', type, handler])
    },
    forumEventHandler: function handleForumEvent() {},
    forumRealtimeStore: {
      trackDiscussionIds(ids) {
        calls.push(['track-discussion-ids', ids])
      },
      untrackDiscussionIds(ids) {
        calls.push(['untrack-discussion-ids', ids])
      },
    },
    getCurrentDiscussionIds() {
      return [1, 3]
    },
    readStateHandler: function handleReadState() {},
    removeWindowEventListener(type, handler) {
      calls.push(['remove-window-event-listener', type, handler])
    },
  })

  return {
    calls,
    lifecycle,
  }
}

test('discussion list realtime lifecycle registers browser listeners on mount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleMounted()

  assert.equal(harness.calls.length, 2)
  assert.deepEqual(harness.calls.map(([type, eventType]) => [type, eventType]), [
    ['add-window-event-listener', 'bias:discussion-read-state-updated'],
    ['add-window-event-listener', 'bias:forum-event'],
  ])
})

test('discussion list realtime lifecycle clears tracked ids and listeners on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.equal(harness.calls.length, 3)
  assert.deepEqual(harness.calls.map(([type, eventType]) => [type, eventType]), [
    ['untrack-discussion-ids', [1, 3]],
    ['remove-window-event-listener', 'bias:discussion-read-state-updated'],
    ['remove-window-event-listener', 'bias:forum-event'],
  ])
})

test('discussion list realtime lifecycle diffs tracked discussion ids', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.syncTrackedDiscussionIds([2, 3, 4], [1, 3])

  assert.deepEqual(harness.calls, [
    ['untrack-discussion-ids', [1]],
    ['track-discussion-ids', [2, 4]],
  ])
})
