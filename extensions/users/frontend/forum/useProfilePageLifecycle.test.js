import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfilePageLifecycle } from './useProfilePageLifecycle.js'

function createLifecycleHarness() {
  const calls = []
  const lifecycle = createProfilePageLifecycle({
    addForumEventListener() {
      calls.push('add-forum-event-listener')
    },
    cleanupTrackedDiscussions() {
      calls.push('cleanup-tracked-discussions')
    },
    async refreshProfile() {
      calls.push('refresh-profile')
    },
    removeForumEventListener() {
      calls.push('remove-forum-event-listener')
    },
    resetProfileScope() {
      calls.push('reset-profile-scope')
    },
  })

  return {
    calls,
    lifecycle,
  }
}

test('profile page lifecycle refreshes and registers forum event listener on mount', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleMounted()

  assert.deepEqual(harness.calls, [
    'refresh-profile',
    'add-forum-event-listener',
  ])
})

test('profile page lifecycle clears listeners and tracked discussions on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.deepEqual(harness.calls, [
    'remove-forum-event-listener',
    'cleanup-tracked-discussions',
  ])
})

test('profile page lifecycle resets page scope before refreshing on route profile change', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleRouteProfileChange()

  assert.deepEqual(harness.calls, [
    'reset-profile-scope',
    'refresh-profile',
  ])
})
