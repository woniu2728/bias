import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState.js'
import {
  bootstrapEnabledAdminExtensions,
  resetAdminExtensionRuntimeContributions,
  resetLoadedAdminExtensions,
} from './extensionBootstrap.js'
import { createAdminExtensionApp } from './extensionApp.js'
import { createRuntimeApplication } from '../common/application.js'
import { createAdminRuntimeRegistry } from './runtimeRegistry.js'
import {
  Exports as AdminSdkExports,
  ItemList as AdminSdkItemList,
  createAdminRuntimeRegistry as createAdminRuntimeRegistryFromSdk,
} from './sdk.js'
import {
  getAdminRoutes,
  registerAdminRoute,
} from './registry/routes.js'
import { resetAdminExtensionAppRuntime } from './extensionApp.js'

test('createAdminExtensionApp exposes public admin extension APIs', () => {
  const router = { name: 'router' }
  const extension = { id: 'tags' }
  const loadedExtensionIds = new Set()
  const routes = []
  const registry = {
    adminApi: { get() {} },
    registerAdminRoute(route) {
      routes.push(route)
    },
  }
  const app = createAdminExtensionApp({ extension, loadedExtensionIds, registry, router })
  app.registry.for('tags').registerSetting({ key: 'tags.enabled', label: 'Tags' }, 10)
  app.registry.registerPage({ name: 'admin-tags', path: '/admin/tags' })

  assert.equal(app.extension, extension)
  assert.equal(app.router, router)
  assert.equal(app.loadedExtensionIds, loadedExtensionIds)
  assert.equal(typeof app.api.get, 'function')
  assert.equal(typeof app.registry.registerAdminRoute, 'function')
  assert.equal(typeof app.initializers.add, 'function')
  assert.equal(typeof app.extend, 'function')
  assert.equal(typeof app.override, 'function')
  assert.equal(typeof app.ItemList, 'function')
  assert.equal(typeof app.registry.list, 'function')
  assert.equal(typeof app.items.add, 'function')
  assert.equal(typeof app.exportRegistry.onLoad, 'function')
  assert.equal(typeof app.cache, 'object')
  assert.equal(typeof app.alerts.warning, 'function')
  assert.equal(typeof app.translator.trans, 'function')
  assert.equal(typeof app.errors.list, 'function')
  assert.equal(app.registry.getSettings('tags')[0].extensionId, 'tags')
  assert.equal(routes[0].extensionId, 'tags')
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

test('admin extension app exposes scoped list registry and cleans it on reset', () => {
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const app = createAdminExtensionApp({
    app: runtimeApp,
    extension: { id: 'admin-items' },
    registry: { adminApi: {} },
  })

  app.registry.add('toolbar-actions', { key: 'inspect', label: 'Inspect' }, 30)

  const actions = app.registry.get('toolbar-actions')
  assert.equal(actions.length, 1)
  assert.equal(actions[0].extensionId, 'admin-items')
  assert.equal(actions[0].label, 'Inspect')

  resetAdminExtensionAppRuntime('admin-items', { app })
  assert.deepEqual(app.registry.get('toolbar-actions'), [])
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

test('resetAdminExtensionRuntimeContributions removes scoped admin routes and items', () => {
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const app = createAdminExtensionApp({
    app: runtimeApp,
    extension: { id: 'scoped' },
    registry: { adminApi: {} },
  })
  registerAdminRoute({
    path: '/admin/scoped',
    name: 'admin-scoped',
    label: 'Scoped',
    extensionId: 'scoped',
  })
  app.registry.add('toolbar-actions', { key: 'inspect', label: 'Inspect' })

  assert.equal(getAdminRoutes().some(route => route.name === 'admin-scoped'), true)
  assert.equal(app.registry.get('toolbar-actions').some(item => item.key === 'inspect'), true)
  resetAdminExtensionRuntimeContributions('scoped', { app })
  assert.equal(getAdminRoutes().some(route => route.name === 'admin-scoped'), false)
  assert.equal(app.registry.get('toolbar-actions').some(item => item.key === 'inspect'), false)
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
  registry.registerSetting({ key: 'alpha_low', label: 'Low' }, 1)
  registry.setSetting('alpha_setting', original => ({ ...original, label: 'Updated' }))
  registry.setSettingPriority('alpha_setting', 10)
  registry.registerPermission({ permission: 'alpha.use', label: 'Use alpha' }, 'moderate', 30)
  registry.registerPermission({ permission: 'alpha.low', label: 'Low alpha' }, 'moderate', 1)
  registry.registerPermission({ id: 'alpha.view', label: 'View alpha' }, 'view', 40)
  registry.setPermissionPriority('alpha.use', 'moderate', 15)
  registry.registerSetting(() => 'custom alpha', 30, 'alpha_custom')
  registry.registerPage({ name: 'admin-alpha', path: '/admin/alpha' })
  registry.generalIndex.for('alpha').add('settings', [{ key: 'alpha_setting' }])

  const settings = registry.getSettings('alpha')
  assert.equal(settings[0].key, 'alpha_custom')
  assert.equal(settings[0](), 'custom alpha')
  assert.deepEqual(settings.slice(1), [{
    key: 'alpha_setting',
    label: 'Updated',
    priority: 10,
    custom: false,
  }, {
    key: 'alpha_low',
    label: 'Low',
    priority: 1,
    custom: false,
  }])
  assert.deepEqual(registry.getPermissions('alpha', 'moderate'), [{
    permission: 'alpha.use',
    label: 'Use alpha',
    type: 'moderate',
    priority: 15,
  }, {
    permission: 'alpha.low',
    label: 'Low alpha',
    type: 'moderate',
    priority: 1,
  }])
  assert.equal(registry.getAllPermissions('moderate').toArray()[0].permission, 'alpha.use')
  assert.equal(registry.getExtensionPermissions('alpha', 'view').toArray()[0].permission, 'alpha.view')
  assert.equal(registry.getPages('alpha')[0].path, '/admin/alpha')
  assert.equal(routes[0].path, '/admin/alpha')
  assert.deepEqual(registry.generalIndex.get('alpha', 'settings'), [{ key: 'alpha_setting' }])
})

test('admin public sdk exposes stable extension developer APIs', () => {
  const list = new AdminSdkItemList()
  list.add('high', { label: 'High' }, 20)
  list.add('low', { label: 'Low' }, 1)

  assert.equal(list.toArray()[0].itemName, 'high')
  assert.equal(typeof AdminSdkExports, 'function')
  assert.equal(typeof createAdminRuntimeRegistryFromSdk, 'function')
})

test('bootstrapEnabledAdminExtensions runs runtime application initializers', async () => {
  resetLoadedAdminExtensions()
  const calls = []
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
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

  try {
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
          extend: [{
            extend(app) {
            assert.equal(app.initializers, runtimeApp.initializers)
            assert.equal(runtimeApp.currentInitializerExtension, 'runtime-admin')
            app.initializers.add('runtime-admin', extensionApp => {
              calls.push(extensionApp.application.currentInitializerExtension)
              calls.push(extensionApp.extension.id)
            }, 10)
            assert.equal(app.initializers.toArray()[0].itemName, 'runtime-admin/0')
            },
          }],
        }),
      },
    })

    assert.deepEqual(calls, ['runtime-admin', 'runtime-admin'])
    assert.equal(runtimeApp.currentInitializerExtension, null)
    assert.equal(runtimeApp.initializers.list().length, 0)
    assert.equal(Array.isArray(runtimeApp.extensions['runtime-admin'].modules.admin.extend), true)
    assert.equal(globalThis.bias.extensions['runtime-admin'], runtimeApp.extensions['runtime-admin'])
  } finally {
    globalThis.bias = previousBias
  }
})
