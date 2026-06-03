import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState.js'
import {
  bootstrapEnabledAdminExtensions,
  resetLoadedAdminExtensions,
} from './extensionBootstrap.js'
import { createAdminExtensionApp } from './extensionApp.js'
import { createRuntimeApplication } from '../common/application.js'
import { createAdminRuntimeRegistry } from './runtimeRegistry.js'
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

test('createAdminExtensionApp reuses runtime application services', () => {
  const runtimeApp = createRuntimeApplication({
    kind: 'admin',
    api: { get() {} },
    store: { name: 'store' },
  })
  const app = createAdminExtensionApp({
    app: runtimeApp,
    extension: { id: 'diagnostics' },
    registry: { adminApi: {} },
  })

  app.cache.shared = true

  assert.equal(app.application, runtimeApp)
  assert.equal(runtimeApp.cache.shared, true)
  assert.equal(app.store.name, 'store')
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

test('admin runtime registry scopes settings permissions pages and general index', () => {
  const routes = []
  const registry = createAdminRuntimeRegistry({
    registerAdminRoute(route) {
      routes.push(route)
    },
  })

  registry.for('alpha')
  registry.registerSetting({ key: 'alpha_setting', label: 'Alpha' }, 20)
  registry.setSetting('alpha_setting', original => ({ ...original, label: 'Updated' }))
  registry.setSettingPriority('alpha_setting', 10)
  registry.registerPermission({ permission: 'alpha.use', label: 'Use alpha' }, 'moderate', 30)
  registry.setPermissionPriority('alpha.use', 'moderate', 15)
  registry.registerPage({ name: 'admin-alpha', path: '/admin/alpha' })
  registry.generalIndex.for('alpha').add('settings', [{ key: 'alpha_setting' }])

  assert.deepEqual(registry.getSettings('alpha'), [{
    key: 'alpha_setting',
    label: 'Updated',
    priority: 10,
    custom: false,
  }])
  assert.deepEqual(registry.getPermissions('alpha', 'moderate'), [{
    permission: 'alpha.use',
    label: 'Use alpha',
    type: 'moderate',
    priority: 15,
  }])
  assert.equal(registry.getPages('alpha')[0].path, '/admin/alpha')
  assert.equal(routes[0].path, '/admin/alpha')
  assert.deepEqual(registry.generalIndex.get('alpha', 'settings'), [{ key: 'alpha_setting' }])
})

test('bootstrapEnabledAdminExtensions runs runtime application initializers', async () => {
  resetLoadedAdminExtensions()
  const calls = []
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const router = {
    addRoute() {},
    hasRoute() {
      return false
    },
    getRoutes() {
      return []
    },
    removeRoute() {},
  }

  await bootstrapEnabledAdminExtensions({
    app: runtimeApp,
    router,
    runtime: { stamp: 'runtime-initializer-test' },
    registry: { adminApi: {} },
    extensions: [{
      id: 'runtime-admin',
      enabled: true,
      frontend_admin_entry: 'extensions/runtime-admin/frontend/admin/index.js',
    }],
    entryModules: {
      '../../../extensions/runtime-admin/frontend/admin/index.js': async () => ({
        bootAdminExtension: async ({ app }) => {
          assert.equal(app.initializers, runtimeApp.initializers)
          app.initializers.add('runtime-admin', extensionApp => {
            calls.push(extensionApp.extension.id)
          })
        },
      }),
    },
  })

  assert.deepEqual(calls, ['runtime-admin'])
  assert.equal(runtimeApp.initializers.list().length, 0)
})
