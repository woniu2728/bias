import test from 'node:test'
import assert from 'node:assert/strict'
import {
  resolveAnchorScrollDelta,
  resolveVisiblePostMetrics,
  settleAnchorScrollPosition,
} from './useDiscussionPostViewportState.js'

test('resolveVisiblePostMetrics prefers closest visible post and interpolated progress', () => {
  const result = resolveVisiblePostMetrics({
    postRects: [
      { number: 10, rect: { top: 80, bottom: 180, height: 100 } },
      { number: 11, rect: { top: 190, bottom: 290, height: 100 } },
      { number: 12, rect: { top: 300, bottom: 400, height: 100 } },
    ],
    viewportTop: 96,
    viewportBottom: 320,
    anchorY: 120,
    maxPostNumber: 40,
    scrollBottom: 500,
    documentBottom: 1200,
  })

  assert.equal(result.trackedPostNumber, 10)
  assert.equal(result.progress > 10, true)
  assert.equal(result.progress < 11, true)
})

test('resolveVisiblePostMetrics pins progress to max when already at page bottom', () => {
  const result = resolveVisiblePostMetrics({
    postRects: [
      { number: 18, rect: { top: 40, bottom: 140, height: 100 } },
      { number: 19, rect: { top: 150, bottom: 250, height: 100 } },
      { number: 20, rect: { top: 260, bottom: 360, height: 100 } },
    ],
    viewportTop: 96,
    viewportBottom: 360,
    anchorY: 120,
    maxPostNumber: 20,
    scrollBottom: 980,
    documentBottom: 1000,
  })

  assert.equal(result.trackedPostNumber, 20)
  assert.equal(result.progress, 20)
})

test('resolveAnchorScrollDelta ignores tiny anchor drift', () => {
  const delta = resolveAnchorScrollDelta({
    anchorTop: 240,
    currentTop: 240.4,
    threshold: 1,
  })

  assert.equal(delta, null)
})

test('settleAnchorScrollPosition keeps correcting until anchor stabilizes', async () => {
  const topSequence = [344, 332, 320]
  const applied = []
  let readCount = 0

  const settled = await settleAnchorScrollPosition({
    anchorTop: 320,
    getCurrentTop: () => {
      const index = Math.min(readCount, topSequence.length - 1)
      const value = topSequence[index]
      readCount += 1
      return value
    },
    scrollBy: delta => {
      applied.push(delta)
    },
    scheduleFrame: callback => callback(),
    maxFrames: 4,
    threshold: 1,
  })

  assert.equal(settled, true)
  assert.deepEqual(applied, [24, 12])
})

test('settleAnchorScrollPosition exits immediately when anchor is already stable', async () => {
  const applied = []

  const settled = await settleAnchorScrollPosition({
    anchorTop: 200,
    getCurrentTop: () => 200,
    scrollBy: delta => {
      applied.push(delta)
    },
    scheduleFrame: callback => callback(),
    maxFrames: 3,
    threshold: 1,
  })

  assert.equal(settled, false)
  assert.deepEqual(applied, [])
})
