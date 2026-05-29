import test from 'node:test'
import assert from 'node:assert/strict'

import {
  loadExtensionAdminEntryModule,
  normalizeExtensionAdminEntry,
  resolveFallbackAdminComponent,
  resolveAdminEntryFactory,
  resolveExtensionAdminComponent,
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

test('loadExtensionAdminEntryModule accepts builtin operation hosts without custom exports', async () => {
  const builtinModule = {}
  const loaded = await loadExtensionAdminEntryModule('builtin:notifications', {
    builtins: {
      'builtin:notifications': builtinModule,
    },
  })

  assert.equal(loaded, builtinModule)
})

test('loadExtensionAdminEntryModule accepts additional builtin operation hosts', async () => {
  const builtinModule = {}
  const loaded = await loadExtensionAdminEntryModule('builtin:likes', {
    builtins: {
      'builtin:likes': builtinModule,
    },
  })

  assert.equal(loaded, builtinModule)
})

test('loadExtensionAdminEntryModule accepts builtin discussion operation hosts', async () => {
  const builtinModule = {}
  const loaded = await loadExtensionAdminEntryModule('builtin:discussions', {
    builtins: {
      'builtin:discussions': builtinModule,
    },
  })

  assert.equal(loaded, builtinModule)
})

test('resolveAdminEntryFactory can expose builtin discussion and post host components', () => {
  const discussionModule = {
    resolvePermissionsPage: 'discussion-permissions',
    resolveOperationsPage: 'discussion-operations',
  }
  const postModule = {
    resolveOperationsPage: 'post-operations',
  }
  const notificationModule = {
    resolveOperationsPage: 'notification-operations',
  }
  const realtimeModule = {
    resolveOperationsPage: 'realtime-operations',
  }

  assert.equal(resolveAdminEntryFactory(discussionModule, 'permissions'), 'discussion-permissions')
  assert.equal(resolveAdminEntryFactory(discussionModule, 'operations'), 'discussion-operations')
  assert.equal(resolveAdminEntryFactory(postModule, 'operations'), 'post-operations')
  assert.equal(resolveAdminEntryFactory(notificationModule, 'operations'), 'notification-operations')
  assert.equal(resolveAdminEntryFactory(realtimeModule, 'operations'), 'realtime-operations')
})

test('loadExtensionAdminEntryModule loads filesystem importer entries', async () => {
  const loaded = await loadExtensionAdminEntryModule('../../../../extensions/sample-hello/frontend/admin/index.js', {
    importers: {
      '../../../../extensions/sample-hello/frontend/admin/index.js': async () => ({
        resolveDetailPage: () => null,
      }),
    },
  })

  assert.equal(typeof loaded.resolveDetailPage, 'function')
})

test('resolveFallbackAdminComponent returns the first matching fallback component', async () => {
  const component = await resolveFallbackAdminComponent(
    { id: 'demo' },
    'settings',
    {
      fallbacks: [
        () => null,
        () => ({ name: 'FallbackSettingsPage' }),
      ],
    },
  )

  assert.equal(component.name, 'FallbackSettingsPage')
})

test('resolveExtensionAdminComponent falls back when admin entry is missing', async () => {
  const component = await resolveExtensionAdminComponent(
    {
      id: 'demo',
      frontend_admin_entry: '',
    },
    'settings',
    {
      fallbacks: [
        () => ({ name: 'GeneratedSettingsPage' }),
      ],
    },
  )

  assert.equal(component.name, 'GeneratedSettingsPage')
})

test('resolveExtensionAdminComponent falls back when admin entry does not export current surface', async () => {
  const component = await resolveExtensionAdminComponent(
    {
      id: 'demo',
      frontend_admin_entry: 'extensions/demo/frontend/admin/index.js',
    },
    'settings',
    {
      importers: {
        '../../../../extensions/demo/frontend/admin/index.js': async () => ({
          resolveDetailPage: () => null,
        }),
      },
      fallbacks: [
        () => ({ name: 'GeneratedSettingsPage' }),
      ],
    },
  )

  assert.equal(component.name, 'GeneratedSettingsPage')
})

test('resolveExtensionAdminComponent can resolve different surface fallbacks', async () => {
  const operationsComponent = await resolveExtensionAdminComponent(
    {
      id: 'demo',
      frontend_admin_entry: '',
    },
    'operations',
    {
      fallbacks: [
        ({ surface }) => (surface === 'operations' ? { name: 'GeneratedOperationsPage' } : null),
      ],
    },
  )

  const permissionsComponent = await resolveExtensionAdminComponent(
    {
      id: 'demo',
      frontend_admin_entry: '',
    },
    'permissions',
    {
      fallbacks: [
        ({ surface }) => (surface === 'permissions' ? { name: 'GeneratedPermissionsPage' } : null),
      ],
    },
  )

  assert.equal(operationsComponent.name, 'GeneratedOperationsPage')
  assert.equal(permissionsComponent.name, 'GeneratedPermissionsPage')
})
