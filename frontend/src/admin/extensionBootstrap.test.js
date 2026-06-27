import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resetLoadedExtensions,
  resetLoadedExtensionsWhenRuntimeChanges,
} from './extensionRuntimeState.js'
import {
  bootstrapEnabledAdminExtensions,
  registerExtensionAdminRoutes,
  resolveAdminRouteComponentKeys,
  resetAdminExtensionRuntimeContributions,
  resetLoadedAdminExtensions,
} from './extensionBootstrap.js'
import {
  createAdminExtensionApp,
  getAdminExtensionInitializers,
  resetAdminExtensionAppRuntime,
} from './extensionApp.js'
import { createRuntimeApplication } from '../common/application.js'
import {
  onLazyModuleLoad,
  registerLazyExtensionModule,
  registerLoadedExtensionModule,
} from '../common/extensionRuntime.js'
import { createAdminRuntimeRegistry } from './runtimeRegistry.js'
import {
  Exports as AdminSdkExports,
} from './sdk.js'
import { ItemList as AdminSdkItemList } from '../common/sdk.js'
import {
  clearAdminRoutesForExtension,
  getAdminRoutes,
  registerAdminRoute,
} from './registry/routes.js'

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

test('resetAdminExtensionRuntimeContributions clears export registry namespace', () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const module = { extend: [] }

  try {
    registerLoadedExtensionModule('admin-tools', module, {
      app: runtimeApp,
      frontend: 'admin',
      entryPath: 'extensions/admin-tools/frontend/admin/index.js',
    })

    assert.equal(runtimeApp.exportRegistry.get('admin-tools', 'admin'), module)
    assert.equal(runtimeApp.exportRegistry.getModule('extensions/admin-tools/frontend/admin/index.js'), module)

    resetAdminExtensionRuntimeContributions('admin-tools', { app: runtimeApp })

    assert.equal(runtimeApp.exportRegistry.get('admin-tools', 'admin'), null)
    assert.equal(runtimeApp.exportRegistry.getModule('extensions/admin-tools/frontend/admin/index.js'), null)
  } finally {
    globalThis.bias = previousBias
  }
})

test('resetAdminExtensionRuntimeContributions clears chunks and loaded lazy modules', async () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }

  try {
    const runtimeApp = createRuntimeApplication({ kind: 'admin' })
    const lazyModule = { name: 'admin-lazy' }
    const ownedModule = { name: 'owned-admin-lazy' }
    const calls = []

    runtimeApp.exportRegistry.onLoadPath('extensions/admin-tools/frontend/admin/lazy.js', loaded => {
      calls.push(loaded)
    })
    runtimeApp.exportRegistry.registerChunk('admin-tools', 'admin-lazy', {
      'frontend/admin/lazy.js': async () => lazyModule,
    })
    registerLazyExtensionModule('admin-shared-lazy-key', ownedModule, { extensionId: 'admin-tools' })

    resetAdminExtensionRuntimeContributions('admin-tools', { app: runtimeApp })

    await assert.rejects(
      runtimeApp.exportRegistry.asyncModuleImport('extensions/admin-tools/frontend/admin/lazy.js'),
      /No chunk found/,
    )
    runtimeApp.exportRegistry.registerModule('extensions/admin-tools/frontend/admin/lazy.js', lazyModule)
    onLazyModuleLoad('admin-shared-lazy-key', loaded => calls.push(loaded))

    assert.equal(globalThis.bias.reg.getModule('admin-shared-lazy-key'), null)
    assert.deepEqual(calls, [])
  } finally {
    globalThis.bias = previousBias
  }
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

test('bootstrapEnabledAdminExtensions runs initializer-only entry modules', async () => {
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
      runtime: { stamp: 'initializer-only-test' },
      registry: { adminApi: {} },
      extensions: [{
        id: 'initializer-only',
        enabled: true,
        frontend_admin_entry: 'extensions/initializer-only/frontend/admin/index.js',
      }],
      entryModules: {
        '../../../extensions/initializer-only/frontend/admin/index.js': async () => {
          getAdminExtensionInitializers().add('initializer-only', extensionApp => {
            calls.push(extensionApp.extension.id)
            calls.push(extensionApp.application.kind)
          })
          return { ready: true }
        },
      },
    })

    assert.deepEqual(calls, ['initializer-only', 'admin'])
    assert.equal(runtimeApp.extensions['initializer-only'].modules.admin.ready, true)
    assert.equal(globalThis.bias.extensions['initializer-only'], runtimeApp.extensions['initializer-only'])
  } finally {
    getAdminExtensionInitializers().clear('initializer-only')
    globalThis.bias = previousBias
  }
})

test('registerExtensionAdminRoutes resolves extension-owned route components from generated importers', async () => {
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const component = { name: 'AdminRoutePage' }
  const extension = {
    id: 'admin-route-demo',
    frontend_admin_entry: 'extensions/admin-route-demo/frontend/admin/index.js',
    frontend_routes: [{
      frontend: 'admin',
      path: '/admin/route-demo',
      name: 'admin-route-demo.page',
      component: './Page.vue',
      title: 'Route Demo',
      description: 'Demo route',
      order: 42,
    }],
  }

  try {
    assert.deepEqual(resolveAdminRouteComponentKeys('./Page.vue', extension), [
      'admin-route-demo:./Page.vue',
      'admin-route-demo:extensions/admin-route-demo/frontend/admin/Page.vue',
      'extensions/admin-route-demo/frontend/admin/Page.vue',
      '../../../extensions/admin-route-demo/frontend/admin/Page.vue',
      './Page.vue',
    ])

    const registered = registerExtensionAdminRoutes(null, extension, {
      app: runtimeApp,
      importers: {
        '../../../extensions/admin-route-demo/frontend/admin/Page.vue': async () => ({ default: component }),
      },
    })

    assert.deepEqual(registered, ['admin-route-demo.page'])
    const route = getAdminRoutes().find(item => item.name === 'admin-route-demo.page')
    assert.equal(route.path, '/admin/route-demo')
    assert.equal(route.label, 'Route Demo')
    assert.equal(route.navDescription, 'Demo route')
    assert.equal(route.navOrder, 42)
    assert.equal(route.extensionId, 'admin-route-demo')
    assert.equal(await route.component(), component)
    assert.equal(runtimeApp.routes.definitions['admin-route-demo.page'].path, '/admin/route-demo')
    assert.equal(runtimeApp.routes.definitions['admin-route-demo.page'].frontend, 'admin')
    assert.equal(runtimeApp.routes.definitions['admin-route-demo.page'].moduleId, 'admin-route-demo')
  } finally {
    clearAdminRoutesForExtension('admin-route-demo')
  }
})

test('bootstrapEnabledAdminExtensions registers backend-only admin routes', async () => {
  resetLoadedAdminExtensions()
  const component = { name: 'BackendOnlyAdminPage' }
  const addedRoutes = []
  const router = {
    addRoute(route) {
      addedRoutes.push(route)
    },
    hasRoute() {
      return false
    },
    getRoutes() {
      return []
    },
    removeRoute() {},
  }

  try {
    const result = await bootstrapEnabledAdminExtensions({
      router,
      runtime: { stamp: 'backend-only-admin-routes' },
      registry: { adminApi: {} },
      extensions: [{
        id: 'admin-backend-only',
        enabled: true,
        frontend_routes: [{
          frontend: 'admin',
          path: '/admin/backend-only',
          name: 'admin-backend-only.page',
          component: 'extensions/admin-backend-only/frontend/admin/Page.vue',
          title: 'Backend Only',
        }],
      }],
      entryModules: {
        '../../../extensions/admin-backend-only/frontend/admin/Page.vue': async () => ({ default: component }),
      },
    })

    assert.equal(result.addedRouteCount, 1)
    assert.equal(addedRoutes[0].name, 'admin-backend-only.page')
    assert.equal(await addedRoutes[0].component(), component)
  } finally {
    clearAdminRoutesForExtension('admin-backend-only')
  }
})

test('bootstrapEnabledAdminExtensions resolves backend-only route components from frontend outputs', async () => {
  resetLoadedAdminExtensions()
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  const component = { name: 'BackendOnlyOutputPage' }
  const addedRoutes = []
  const router = {
    addRoute(route) {
      addedRoutes.push(route)
    },
    hasRoute() {
      return false
    },
    getRoutes() {
      return []
    },
    removeRoute() {},
  }

  try {
    const result = await bootstrapEnabledAdminExtensions({
      app: runtimeApp,
      router,
      runtime: { stamp: 'backend-only-admin-output-routes' },
      registry: { adminApi: {} },
      extensions: [{
        id: 'admin-output-route',
        enabled: true,
        frontend_outputs: {
          admin: {
            revision: 'rev-route',
            chunks: [{
              file: 'assets/admin-output-route-page.js',
              module_id: 'frontend/admin/Page.vue',
            }],
          },
        },
        frontend_routes: [{
          frontend: 'admin',
          path: '/admin/output-route',
          name: 'admin-output-route.page',
          component: './Page.vue',
          title: 'Output Route',
        }],
      }],
      entryModules: {},
    })

    runtimeApp.exportRegistry.registerChunk('admin-output-route', 'admin/assets/admin-output-route-page.js', {
      'frontend/admin/Page.vue': async () => ({ default: component }),
    })

    assert.equal(result.addedRouteCount, 1)
    assert.equal(addedRoutes[0].name, 'admin-output-route.page')
    assert.equal(await addedRoutes[0].component(), component)
    assert.equal(runtimeApp.routes.definitions['admin-output-route.page'].path, '/admin/output-route')
    assert.equal(runtimeApp.routes.definitions['admin-output-route.page'].frontend, 'admin')
  } finally {
    clearAdminRoutesForExtension('admin-output-route')
  }
})

test('registerExtensionAdminRoutes removes declared admin routes', () => {
  const removed = []
  const runtimeApp = createRuntimeApplication({ kind: 'admin' })
  runtimeApp.routes.definitions['admin-route-remove.page'] = {
    path: '/admin/remove-me',
    name: 'admin-route-remove.page',
    extensionId: 'admin-route-remove',
  }
  const router = {
    hasRoute(name) {
      return name === 'admin-route-remove.page'
    },
    removeRoute(name) {
      removed.push(name)
    },
  }

  try {
    registerAdminRoute({
      path: '/admin/remove-me',
      name: 'admin-route-remove.page',
      label: 'Remove me',
      extensionId: 'admin-route-remove',
    })
    assert.equal(getAdminRoutes().some(route => route.name === 'admin-route-remove.page'), true)

    const registered = registerExtensionAdminRoutes(router, {
      id: 'admin-route-remove',
      frontend_routes: [{
        frontend: 'admin',
        name: 'admin-route-remove.page',
        removed: true,
      }],
    }, { app: runtimeApp })

    assert.deepEqual(registered, ['admin-route-remove.page'])
    assert.deepEqual(removed, ['admin-route-remove.page'])
    assert.equal(getAdminRoutes().some(route => route.name === 'admin-route-remove.page'), false)
    assert.equal(runtimeApp.routes.definitions['admin-route-remove.page'], undefined)
  } finally {
    clearAdminRoutesForExtension('admin-route-remove')
  }
})
