import test from 'node:test'
import assert from 'node:assert/strict'

import {
  loadExtensionAdminEntryModule,
  normalizeExtensionAdminEntry,
  resolveAdminEntryFactory,
} from './entryResolver.js'


test('normalizeExtensionAdminEntry keeps builtin entries and rewrites extension paths', () => {
  assert.equal(normalizeExtensionAdminEntry('builtin:tags'), 'builtin:tags')
  assert.equal(
    normalizeExtensionAdminEntry('extensions/sample-hello/frontend/admin/index.js'),
    '../../../../extensions/sample-hello/frontend/admin/index.js',
  )
})

test('resolveAdminEntryFactory maps detail and host surfaces to the matching export', () => {
  const module = {
    resolveDetailPage: 'detail',
    resolveSettingsPage: 'settings',
    resolvePermissionsPage: 'permissions',
    resolveOperationsPage: 'operations',
  }

  assert.equal(resolveAdminEntryFactory(module, 'detail'), 'detail')
  assert.equal(resolveAdminEntryFactory(module, 'settings'), 'settings')
  assert.equal(resolveAdminEntryFactory(module, 'permissions'), 'permissions')
  assert.equal(resolveAdminEntryFactory(module, 'operations'), 'operations')
})

test('loadExtensionAdminEntryModule prefers builtin registry for builtin entries', async () => {
  const builtinModule = { resolveDetailPage: () => null }
  const loaded = await loadExtensionAdminEntryModule('builtin:sample', {
    builtins: {
      'builtin:sample': builtinModule,
    },
  })

  assert.equal(loaded, builtinModule)
})
