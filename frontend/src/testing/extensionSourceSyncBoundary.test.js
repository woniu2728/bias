import test from 'node:test'
import assert from 'node:assert/strict'
import { collectHostExtensionSourceBoundaryViolations } from '../../scripts/checkExtensionFrontendBoundary.mjs'

test('host production frontend loads extension source from generated site extensions only', () => {
  assert.deepEqual(collectHostExtensionSourceBoundaryViolations(), [])
})
