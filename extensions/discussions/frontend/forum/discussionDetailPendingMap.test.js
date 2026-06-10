import test from 'node:test'
import assert from 'node:assert/strict'
import {
  addPendingPostAction,
  hasPendingPostAction,
  removePendingPostAction,
} from './discussionDetailPendingMap.js'

test('pending post action helpers avoid duplicate ids and remove completed ids', () => {
  const initial = []
  const afterFirstAdd = addPendingPostAction(initial, 7)
  const afterDuplicateAdd = addPendingPostAction(afterFirstAdd, 7)
  const afterSecondAdd = addPendingPostAction(afterDuplicateAdd, 9)
  const afterRemove = removePendingPostAction(afterSecondAdd, 7)

  assert.equal(hasPendingPostAction(afterFirstAdd, 7), true)
  assert.deepEqual(afterDuplicateAdd, [7])
  assert.deepEqual(afterSecondAdd, [7, 9])
  assert.deepEqual(afterRemove, [9])
  assert.equal(hasPendingPostAction(afterRemove, 7), false)
})
