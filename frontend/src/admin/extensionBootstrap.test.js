import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState.js'
import { createAdminExtensionApp } from './extensionApp.js'
import {
  clearAdminRoutesForExtension,
  getAdminRoutes,
  registerAdminRoute,
} from './registry/routes.js'
import { resetAdminExtensionAppRuntime } from './extensionApp.js'

test('createAdminExtensionApp exposes public admin extension APIs', () => {
  const router = { name: 'router' }
  const extension = { id: 'tags' }
  const loadedExtensionIds = new Set()
  const registry = {
    adminApi: { get() {} },
    registerAdminRoute() {},
  }
  const app = createAdminExtensionApp({ extension, loadedExtensionIds, registry, router })

  assert.equal(app.extension, extension)
  assert.equal(app.router, router)
  assert.equal(app.loadedExtensionIds, loadedExtensionIds)
  assert.equal(typeof app.api.get, 'function')
  assert.equal(typeof app.registry.registerAdminRoute, 'function')
  assert.equal(typeof app.initializers.add, 'function')
  assert.equal(typeof app.extend, 'function')
  assert.equal(typeof app.override, 'function')
  assert.equal(typeof app.cache, 'object')
  assert.equal(typeof app.alerts.warning, 'function')
  assert.equal(typeof app.translator.trans, 'function')
  assert.equal(typeof app.errors.list, 'function')
})

test('resetLoadedAdminExtensionsWhenRuntimeChanges clears admin boot state on stamp change', () => {
  const loadedIds = new Set(['tags'])
  resetLoadedExtensions(loadedIds)

  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), true)
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), false)
  loadedIds.add('tags')
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'two' }), true)
  assert.equal(loadedIds.size, 0)
})

test('resetAdminExtensionRuntimeContributions removes scoped admin routes', () => {
  registerAdminRoute({
    path: '/admin/scoped',
    name: 'admin-scoped',
    label: 'Scoped',
    extensionId: 'scoped',
  })

  assert.equal(getAdminRoutes().some(route => route.name === 'admin-scoped'), true)
  clearAdminRoutesForExtension('scoped')
  assert.equal(getAdminRoutes().some(route => route.name === 'admin-scoped'), false)
})

test('admin extension app runs scoped initializers and resets patches', async () => {
  const target = {
    value() {
      return ['base']
    },
  }
  const app = createAdminExtensionApp({
    extension: { id: 'scoped' },
    registry: { adminApi: {} },
  })
  app.initializers.add('scoped', () => {
    app.override(target, 'value', original => [...original(), 'patched'])
  })
  await app.initializers.run(app)
  assert.deepEqual(target.value(), ['base', 'patched'])
  resetAdminExtensionAppRuntime('scoped')
  assert.deepEqual(target.value(), ['base'])
})
