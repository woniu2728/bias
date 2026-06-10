import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionDetailPageLifecycle } from './useDiscussionDetailPageLifecycle.js'

function createLifecycleHarness() {
  const calls = []
  const loading = ref(false)
  const lifecycle = createDiscussionDetailPageLifecycle({
    attachGlobalListeners() {
      calls.push('attach')
    },
    detachGlobalListeners() {
      calls.push('detach')
    },
    loading,
    async refreshDiscussion() {
      calls.push('refresh')
    },
    resetMobileHeader() {
      calls.push('reset-mobile-header')
    },
    resetPostStream() {
      calls.push('reset-post-stream')
    },
    resetScrubberPreview() {
      calls.push('reset-scrubber-preview')
    },
    resetTransientUiState() {
      calls.push('reset-transient-ui')
    },
    async syncNearPostWindow() {
      calls.push('sync-near-post-window')
    },
    syncMobileHeader() {
      calls.push('sync-mobile-header')
    },
    updateVisiblePostFromScroll() {
      calls.push('update-visible-post')
    },
  })

  return {
    calls,
    lifecycle,
    loading,
  }
}

test('discussion detail page lifecycle resets page state before refreshing on route scope change', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleDiscussionScopeChange()

  assert.equal(harness.loading.value, true)
  assert.deepEqual(harness.calls, [
    'reset-mobile-header',
    'reset-post-stream',
    'reset-transient-ui',
    'reset-scrubber-preview',
    'refresh',
  ])
})

test('discussion detail page lifecycle syncs route near without resetting page state', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleNearRouteChange()

  assert.equal(harness.loading.value, false)
  assert.deepEqual(harness.calls, ['sync-near-post-window'])
})

test('discussion detail page lifecycle refreshes, attaches listeners and syncs header on mount', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleMounted()

  assert.deepEqual(harness.calls, [
    'refresh',
    'attach',
    'update-visible-post',
    'sync-mobile-header',
  ])
})

test('discussion detail page lifecycle detaches listeners on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.deepEqual(harness.calls, ['detach'])
})

test('discussion detail page lifecycle exposes dedicated mobile header sync handler', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleHeaderSync()

  assert.deepEqual(harness.calls, ['sync-mobile-header'])
})
