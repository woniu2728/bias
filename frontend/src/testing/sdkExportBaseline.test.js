import test from 'node:test'
import assert from 'node:assert/strict'
import { compareBaseline } from '../../scripts/checkSdkExports.mjs'

const current = {
  schema_version: 1,
  entries: {
    '.': {
      targets: { default: './common.js' },
      exports: ['extend', 'newExport'],
    },
  },
}

test('sdk export baseline requires stability metadata for added exports', () => {
  assert.deepEqual(
    compareBaseline(
      {
        schema_version: 2,
        entries: {
          '.': {
            targets: { default: './common.js' },
            exports: {
              extend: { stability: 'stable' },
            },
          },
        },
      },
      current,
    ),
    ['SDK export added without baseline stability: @bias/core:newExport'],
  )
})

test('sdk export baseline rejects unknown stability values', () => {
  assert.deepEqual(
    compareBaseline(
      {
        schema_version: 2,
        entries: {
          '.': {
            targets: { default: './common.js' },
            exports: {
              extend: { stability: 'preview' },
              newExport: { stability: 'experimental' },
            },
          },
        },
      },
      current,
    ),
    ['SDK export missing valid stability: @bias/core:extend'],
  )
})
