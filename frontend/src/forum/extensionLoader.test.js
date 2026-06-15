import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyExtensionDocumentPayload,
  loadEnabledForumExtensions,
  loadExtensionForumEntryModule,
  getForumInitializers,
  normalizeExtensionDocumentPayload,
  normalizeExtensionForumEntry,
  registerExtensionForumRoutes,
  resolveForumRouteComponentKeys,
  resetForumExtensionRuntimeContributions,
  resetLoadedExtensionsWhenRuntimeChanges,
  validateForumExtensionModule,
} from './extensionLoader.js'
import { getForumNavItems, registerForumNavItem } from './frontendRegistry.js'
import {
  clearExtensionRuntimeErrors,
  extendMethod,
  getExtensionRuntimeErrors,
  onLazyModuleLoad,
  registerLazyExtensionModule,
  registerLoadedExtensionModule,
} from '../common/extensionRuntime.js'
import { ApplicationRequestError, createRuntimeApplication } from '../common/application.js'
import { ModelExtender, ResourceModel, StoreExtender } from '../common/resourceModel.js'
import extenders, { Exports, Model, PostTypes, ResourceModelExtender, Search, Store, ThemeMode, extendAdmin, extendForum } from '../common/extenders.js'
import {
  AdminExtender,
  ExportsExtender,
  ForumExtender,
  NotificationExtender,
  PostTypesExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
} from '../common/frontendExtenders.js'
import { GroupModel, UserModel } from '../common/resourceModels.js'

function createTestResourceStore() {
  const buckets = {}
  return {
    buckets,
    upsert(type, item) {
      buckets[type] ||= {}
      buckets[type][String(item.id)] = {
        ...(buckets[type][String(item.id)] || {}),
        ...item,
      }
      return buckets[type][String(item.id)]
    },
    get(type, id) {
      return buckets[type]?.[String(id)] || null
    },
    remove(type, id) {
      delete buckets[type]?.[String(id)]
    },
    mergePayload(payload = {}, explicitType = '') {
      if (!explicitType) return []
      return (Array.isArray(payload) ? payload : [payload]).map(item => this.upsert(explicitType, item))
    },
  }
}

test('normalizeExtensionForumEntry rewrites extension paths', () => {
  assert.equal(
    normalizeExtensionForumEntry('extensions/manifest-demo/frontend/forum/index.js'),
    '../../../extensions/manifest-demo/frontend/forum/index.js',
  )
  assert.equal(normalizeExtensionForumEntry(''), '')
})

test('loadExtensionForumEntryModule loads filesystem importer entries', async () => {
  const loaded = await loadExtensionForumEntryModule('../../../extensions/manifest-demo/frontend/forum/index.js', {
    importers: {
      '../../../extensions/manifest-demo/frontend/forum/index.js': async () => ({
        boot: true,
      }),
    },
  })

  assert.equal(loaded.boot, true)
})

test('loadExtensionForumEntryModule resolves Vite glob importer path variants', async () => {
  const loaded = await loadExtensionForumEntryModule('../../../extensions/points/frontend/forum/index.js', {
    importers: {
      '../../extensions/points/frontend/forum/index.js': async () => ({
        loaded: 'points',
      }),
    },
  })

  assert.equal(loaded.loaded, 'points')
})

test('validateForumExtensionModule allows initializer-only modules', () => {
  assert.doesNotThrow(() => validateForumExtensionModule({}))
  assert.doesNotThrow(() => validateForumExtensionModule({ extend: [] }))
})

test('runtime application normalizes extension module export shapes', async () => {
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  const calls = []

  await runtimeApp.bootExtensions({
    named: {
      extend: {
        extend(app, extension) {
          calls.push(['named', app.kind, extension.name])
        },
      },
    },
    defaultArray: {
      default: [{
        extend(app, extension) {
          calls.push(['default-array', app.kind, extension.name])
        },
      }],
    },
    defaultModule: {
      default: {
        extend: [{
          extend(app, extension) {
            calls.push(['default-module', app.kind, extension.name])
          },
        }],
      },
    },
    functionExtender: {
      extend(app, extension) {
        calls.push(['function', app.kind, extension.name])
      },
    },
  })

  assert.deepEqual(calls, [
    ['named', 'forum', 'named'],
    ['default-array', 'forum', 'defaultArray'],
    ['default-module', 'forum', 'defaultModule'],
    ['function', 'forum', 'functionExtender'],
  ])
})

test('normalizeExtensionDocumentPayload extracts document runtime contracts', () => {
  const normalized = normalizeExtensionDocumentPayload({
    extension_document: {
      preloads: ['/assets/a.css', null],
      document_attributes: {
        dataExtension: 'enabled',
      },
      title_drivers: [
        { extension_id: 'alpha', driver: 'titleDriver' },
        { extension_id: 'empty' },
      ],
      content_callbacks: [
        { extension_id: 'alpha', callback: 'contentCallback', priority: 10 },
        { extension_id: 'beta', callback: 'earlyContent', priority: 30 },
        {},
      ],
    },
  })

  assert.deepEqual(normalized.preloads, ['/assets/a.css'])
  assert.deepEqual(normalized.documentAttributes, { dataExtension: 'enabled' })
  assert.deepEqual(normalized.titleDrivers, [{ extension_id: 'alpha', driver: 'titleDriver' }])
  assert.deepEqual(normalized.contentCallbacks, [
    { extension_id: 'beta', callback: 'earlyContent', priority: 30 },
    { extension_id: 'alpha', callback: 'contentCallback', priority: 10 },
  ])
})

test('applyExtensionDocumentPayload writes preloads and document attributes', () => {
  const links = []
  const attributes = {}
  const documentRef = {
    head: {
      appendChild(link) {
        links.push(link)
      },
    },
    documentElement: {
      setAttribute(key, value) {
        attributes[key] = value
      },
    },
    createElement(tag) {
      return {
        tag,
        attrs: {},
        setAttribute(key, value) {
          this.attrs[key] = value
        },
      }
    },
  }

  const applied = applyExtensionDocumentPayload({
    extension_document: {
      preloads: [
        {
          href: '/assets/alpha.css',
          as: 'style',
          crossOrigin: 'anonymous',
        },
      ],
      document_attributes: {
        dataExtensionRuntime: 'alpha',
      },
    },
  }, { documentRef })

  assert.equal(applied.preloads.length, 1)
  assert.equal(links.length, 1)
  assert.equal(links[0].tag, 'link')
  assert.equal(links[0].attrs.rel, 'preload')
  assert.equal(links[0].attrs.href, '/assets/alpha.css')
  assert.equal(links[0].attrs.as, 'style')
  assert.equal(links[0].attrs['cross-origin'], 'anonymous')
  assert.equal(links[0].attrs['data-bias-extension-preload'], 'true')
  assert.equal(attributes['data-extension-runtime'], 'alpha')
})

test('loadEnabledForumExtensions loads enabled extension entries once and applies payload', async () => {
  const calls = []
  const forumStore = {
    applied: null,
    applyPublicSettings(payload) {
      this.applied = payload
    },
  }

  const payload = {
    enabled_extensions: [
      {
        id: 'alpha',
        frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
      },
      {
        id: 'alpha',
        frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
      },
    ],
    extension_document: {
      preloads: ['/assets/alpha.css'],
    },
  }

  const result = await loadEnabledForumExtensions({
    forumStore,
    fetchPayload: async () => payload,
    importers: {
      '../../../extensions/alpha/frontend/forum/index.js': async () => {
        calls.push('alpha')
        return {
          extend: [{ extend: app => calls.push(app.extension.id) }],
        }
      },
    },
  })

  assert.equal(calls.length, 2)
  assert.equal(result.loadedExtensionIds.has('alpha'), true)
  assert.equal(forumStore.applied, payload)
  assert.deepEqual(result.extensionDocument.preloads, ['/assets/alpha.css'])
})

test('loadEnabledForumExtensions runs initializer-only entry modules', async () => {
  const calls = []
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })

  try {
    await loadEnabledForumExtensions({
      app: runtimeApp,
      fetchPayload: async () => ({
        enabled_extensions: [{
          id: 'initializer-only',
          frontend_forum_entry: 'extensions/initializer-only/frontend/forum/index.js',
        }],
      }),
      importers: {
        '../../../extensions/initializer-only/frontend/forum/index.js': async () => {
          getForumInitializers().add('initializer-only', extensionApp => {
            calls.push(extensionApp.extension.id)
            calls.push(extensionApp.application.kind)
          })
          return { ready: true }
        },
      },
    })

    assert.deepEqual(calls, ['initializer-only', 'forum'])
    assert.equal(runtimeApp.extensions['initializer-only'].modules.forum.ready, true)
    assert.equal(globalThis.bias.extensions['initializer-only'], runtimeApp.extensions['initializer-only'])
  } finally {
    getForumInitializers().clear('initializer-only')
    globalThis.bias = previousBias
  }
})

test('loadEnabledForumExtensions passes public extension app object', async () => {
  let receivedApp = null
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
    router: {
      resolve(location) {
        return { href: `/${location.name}` }
      },
    },
  })
  const extension = {
    id: 'alpha',
    frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
  }
  const navItems = []

  try {
    await loadEnabledForumExtensions({
      app: runtimeApp,
      fetchPayload: async () => ({ enabled_extensions: [extension] }),
      registry: {
        registerForumNavItem(item) {
          navItems.push(item)
        },
      },
      importers: {
        '../../../extensions/alpha/frontend/forum/index.js': async () => ({
          extend: [{
            extend(app) {
            receivedApp = app
            app.registry.for('alpha').registerForumNavItem({ key: 'alpha-link', label: 'Alpha' })
            assert.equal(app.api, receivedApp.api)
            assert.equal(app.registry, receivedApp.registry)
            assert.equal(app.documentRuntime, receivedApp.documentRuntime)
            },
          }],
        }),
      },
    })

    assert.equal(receivedApp.extension, extension)
    assert.equal(typeof receivedApp.registry.registerForumNavItem, 'function')
    assert.equal(typeof receivedApp.documentRuntime.registerContent, 'function')
    assert.equal(typeof receivedApp.initializers.add, 'function')
    assert.equal(typeof receivedApp.extend, 'function')
    assert.equal(typeof receivedApp.override, 'function')
    assert.equal(typeof receivedApp.ItemList, 'function')
    assert.equal(typeof receivedApp.registry.list, 'function')
    assert.equal(typeof receivedApp.items.add, 'function')
    assert.equal(typeof receivedApp.exportRegistry.onLoad, 'function')
    assert.equal(typeof receivedApp.cache, 'object')
    assert.equal(typeof receivedApp.alerts.success, 'function')
    assert.equal(typeof receivedApp.translator.trans, 'function')
    assert.equal(typeof receivedApp.errors.report, 'function')
    assert.equal(receivedApp.route, runtimeApp.route)
    assert.equal(receivedApp.routes, runtimeApp.routes)
    assert.equal(receivedApp.search, runtimeApp.search)
    assert.equal(receivedApp.notificationComponents, runtimeApp.notificationComponents)
    assert.equal(receivedApp.postComponents, runtimeApp.postComponents)
    assert.equal(Array.isArray(runtimeApp.extensions.alpha.modules.forum.extend), true)
    assert.equal(globalThis.bias.extensions.alpha, runtimeApp.extensions.alpha)
    assert.equal(navItems[0].extensionId, 'alpha')
    assert.equal(navItems[0].key, 'alpha-link')
  } finally {
    globalThis.bias = previousBias
  }
})

test('forum extension app exposes scoped priority item lists', async () => {
  let receivedApp = null
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })

  await loadEnabledForumExtensions({
    app: runtimeApp,
    fetchPayload: async () => ({
      enabled_extensions: [{
        id: 'item-list',
        frontend_forum_entry: 'extensions/item-list/frontend/forum/index.js',
      }],
    }),
    importers: {
      '../../../extensions/item-list/frontend/forum/index.js': async () => ({
        extend: [{
          extend(app) {
          receivedApp = app
          const list = new app.ItemList()
          list.add('low', 'low', 1).add('high', 'high', 10)
          const wrappedItems = list.toArray()
          assert.deepEqual(wrappedItems.map(item => item.valueOf()), ['high', 'low'])
          assert.equal(wrappedItems[0].itemName, 'high')
          assert.throws(() => {
            wrappedItems[0].itemName = 'changed'
          }, /read-only/)
          assert.deepEqual(list.toArray(true), ['high', 'low'])
          app.registry.add('discussion-controls', { key: 'alpha', label: 'Alpha' }, 20)
          },
        }],
      }),
    },
  })

  assert.equal(receivedApp.registry.get('discussion-controls')[0].extensionId, 'item-list')
  assert.equal(receivedApp.registry.get('discussion-controls')[0].label, 'Alpha')
  resetForumExtensionRuntimeContributions('item-list', { app: receivedApp })
  assert.deepEqual(receivedApp.registry.get('discussion-controls'), [])
})

test('runtime export registry resolves loaded extension modules', () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  const module = { extend: [] }
  const calls = []

  try {
    runtimeApp.exportRegistry.onLoad('alpha-tools', 'forum', loaded => {
      calls.push(loaded)
    })
    registerLoadedExtensionModule('alpha-tools', module, {
      app: runtimeApp,
      frontend: 'forum',
      entryPath: 'extensions/alpha-tools/frontend/forum/index.js',
    })

    assert.equal(runtimeApp.exportRegistry.get('alpha-tools', 'forum'), module)
    assert.equal(runtimeApp.exportRegistry.getModule('extensions/alpha-tools/frontend/forum/index.js'), module)
    assert.deepEqual(calls, [module])
  } finally {
    globalThis.bias = previousBias
  }
})

test('resetForumExtensionRuntimeContributions clears loaded extension export registry namespace', () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  const module = { extend: [] }

  try {
    registerLoadedExtensionModule('alpha-tools', module, {
      app: runtimeApp,
      frontend: 'forum',
      entryPath: 'extensions/alpha-tools/frontend/forum/index.js',
    })

    assert.equal(runtimeApp.exportRegistry.get('alpha-tools', 'forum'), module)
    assert.equal(runtimeApp.exportRegistry.getModule('extensions/alpha-tools/frontend/forum/index.js'), module)

    resetForumExtensionRuntimeContributions('alpha-tools', { app: runtimeApp })

    assert.equal(runtimeApp.exportRegistry.get('alpha-tools', 'forum'), null)
    assert.equal(runtimeApp.exportRegistry.getModule('extensions/alpha-tools/frontend/forum/index.js'), null)
  } finally {
    globalThis.bias = previousBias
  }
})

test('runtime export registry imports lazy chunk modules by path', async () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }

  try {
    const runtimeApp = createRuntimeApplication({ kind: 'forum' })
    const module = { named: 'lazy-tool' }
    const calls = []

    runtimeApp.exportRegistry.onLoadPath('extensions/alpha-tools/frontend/forum/lazy.js', loaded => {
      calls.push(loaded)
    })
    runtimeApp.exportRegistry.registerChunk('alpha-tools', 'forum-lazy', {
      'frontend/forum/lazy.js': async () => module,
    })

    const loaded = await runtimeApp.exportRegistry.asyncModuleImport('extensions/alpha-tools/frontend/forum/lazy.js')

    assert.equal(loaded, module)
    assert.equal(loaded.default, module)
    assert.deepEqual(calls, [module])
  } finally {
    globalThis.bias = previousBias
  }
})

test('resetForumExtensionRuntimeContributions clears extension chunks and pending path load handlers', async () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }

  try {
    const runtimeApp = createRuntimeApplication({ kind: 'forum' })
    const module = { named: 'lazy-tool' }
    const calls = []

    runtimeApp.exportRegistry.onLoadPath('extensions/alpha-tools/frontend/forum/lazy.js', loaded => {
      calls.push(loaded)
    })
    runtimeApp.exportRegistry.registerChunk('alpha-tools', 'forum-lazy', {
      'frontend/forum/lazy.js': async () => module,
    })

    resetForumExtensionRuntimeContributions('alpha-tools', { app: runtimeApp })

    await assert.rejects(
      runtimeApp.exportRegistry.asyncModuleImport('extensions/alpha-tools/frontend/forum/lazy.js'),
      /No chunk found/,
    )
    runtimeApp.exportRegistry.registerModule('extensions/alpha-tools/frontend/forum/lazy.js', module)
    assert.deepEqual(calls, [])
  } finally {
    globalThis.bias = previousBias
  }
})

test('loadEnabledForumExtensions boots declarative extenders and registers output chunks', async () => {
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })

  await loadEnabledForumExtensions({
    app: runtimeApp,
    fetchPayload: async () => ({
      enabled_extensions: [{
        id: 'declarative',
        frontend_forum_entry: 'extensions/declarative/frontend/forum/index.js',
        frontend_outputs: {
          forum: {
            revision: 'rev123',
            chunks: [{
              key: '../../../extensions/declarative/frontend/forum/lazy.js',
              module_id: 'frontend/forum/lazy.js',
              file: 'assets/declarative-lazy.js',
            }],
          },
        },
      }],
    }),
    importers: {
      '../../../extensions/declarative/frontend/forum/index.js': async () => ({
        extend: [
          new ExportsExtender().module('toolbox', { ready: true }),
        ],
      }),
    },
  })

  assert.deepEqual(runtimeApp.exportRegistry.get('declarative', 'toolbox'), { ready: true })
  assert.equal(
    runtimeApp.exportRegistry.getChunk('declarative', 'forum/assets/declarative-lazy.js').url,
    '/static/frontend/assets/declarative-lazy.js?v=rev123',
  )
})

test('loadEnabledForumExtensions runs scoped initializers', async () => {
  const calls = []
  const target = {
    items() {
      return []
    },
  }

  await loadEnabledForumExtensions({
    fetchPayload: async () => ({
      enabled_extensions: [{
        id: 'scoped',
        frontend_forum_entry: 'extensions/scoped/frontend/forum/index.js',
      }],
    }),
    importers: {
      '../../../extensions/scoped/frontend/forum/index.js': async () => ({
        extend: [{
          extend(app) {
          app.initializers.add('scoped', () => {
            app.extend(target, 'items', (items) => {
              items.push('extended')
            })
            calls.push('initializer')
          })
          },
        }],
      }),
    },
  })

  assert.deepEqual(calls, ['initializer'])
  assert.deepEqual(target.items(), ['extended'])
  assert.equal(getForumInitializers().list().length, 0)
  resetForumExtensionRuntimeContributions('scoped')
  assert.deepEqual(target.items(), [])
})

test('loadEnabledForumExtensions runs runtime application initializers', async () => {
  const calls = []
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })

  await loadEnabledForumExtensions({
    app: runtimeApp,
    fetchPayload: async () => ({
      enabled_extensions: [{
        id: 'runtime-scoped',
        frontend_forum_entry: 'extensions/runtime-scoped/frontend/forum/index.js',
      }],
    }),
    importers: {
      '../../../extensions/runtime-scoped/frontend/forum/index.js': async () => ({
        extend: [{
          extend(app) {
          assert.equal(app.initializers, runtimeApp.initializers)
          app.initializers.add('runtime-scoped', extensionApp => {
            calls.push(extensionApp.extension.id)
          })
          },
        }],
      }),
    },
  })

  assert.deepEqual(calls, ['runtime-scoped'])
  assert.equal(runtimeApp.initializers.list().length, 0)
})

test('runtime application exposes load, beforeMount, preloaded document and title lifecycle', async () => {
  const previousDocument = globalThis.document
  const previousLocation = globalThis.location
  const mergedPayloads = []
  const attributes = {}
  const requests = []

  globalThis.location = { href: 'https://bias.test/current' }
  globalThis.document = {
    title: '',
    documentElement: {
      setAttribute(name, value) {
        attributes[name] = value
      },
    },
  }

  try {
    const runtimeApp = createRuntimeApplication({
      kind: 'forum',
      api: {
        get(url, config) {
          requests.push(['get', url, config?.params])
          return Promise.resolve({ ok: true, url })
        },
      },
      store: {
        mergePayload(payload) {
          mergedPayloads.push(payload)
        },
      },
    })
    const calls = []

    runtimeApp.load({
      api_document: { data: { type: 'forums', id: '1' } },
      resources: [{ type: 'forums', id: '1' }],
      session: { userId: 7 },
    })
    runtimeApp.beforeMount(() => calls.push('before-mount'))
    await runtimeApp.boot(() => calls.push('boot'))

    const preloaded = runtimeApp.preloadedApiDocument()
    runtimeApp.setTitle('Alpha')
    runtimeApp.setTitleCount(3)
    runtimeApp.setColorScheme('dark')
    runtimeApp.setColoredHeader(true)
    const response = await runtimeApp.request({
      method: 'GET',
      url: '/forum',
      params: { include: 'extensions' },
    })

    assert.deepEqual(calls, ['boot', 'before-mount'])
    assert.equal(runtimeApp.session.authenticated, true)
    assert.equal(runtimeApp.session.csrfToken, '')
    assert.deepEqual(preloaded, { data: { type: 'forums', id: '1' } })
    assert.deepEqual(mergedPayloads, [{ data: { type: 'forums', id: '1' } }])
    assert.deepEqual(response, { ok: true, url: '/forum' })
    assert.deepEqual(requests, [['get', '/forum', { include: 'extensions' }]])
    assert.equal(runtimeApp.preloadedApiDocument(), null)
    assert.equal(globalThis.document.title, '(3) Alpha')
    assert.equal(attributes['data-theme'], 'dark')
    assert.equal(attributes['data-colored-header'], 'true')
  } finally {
    globalThis.document = previousDocument
    if (previousLocation === undefined) {
      delete globalThis.location
    } else {
      globalThis.location = previousLocation
    }
  }
})

test('runtime application request handles csrf, response parsing and default errors', async () => {
  const previousConsoleError = console.error
  const requests = []
  const alerts = []
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    api: {
      request(config) {
        requests.push(config)
        if (config.url === '/fail') {
          return Promise.reject({
            response: {
              status: 429,
              headers: { 'X-CSRF-Token': 'fresh-token' },
              data: { errors: [{ detail: 'too many requests' }] },
            },
          })
        }
        return Promise.resolve({
          status: 200,
          headers: { 'X-CSRFToken': 'next-token' },
          data: '{"ok":true}',
        })
      },
    },
    alerts: {
      error(message, options = {}) {
        alerts.push({ message, options })
      },
    },
  })

  console.error = () => {}
  try {
    runtimeApp.load({ session: { userId: 7, csrfToken: 'initial-token' } })

    const response = await runtimeApp.request({
      method: 'POST',
      url: '/save',
      data: { title: 'Alpha' },
      modifyText: text => text.replace('true', 'false'),
    })

    assert.deepEqual(response, { ok: false })
    assert.equal(requests[0].headers['X-CSRFToken'], 'initial-token')
    assert.equal(runtimeApp.session.csrfToken, 'next-token')

    await assert.rejects(
      runtimeApp.request({
        method: 'POST',
        url: '/fail',
        errorHandler(error) {
          assert.equal(error.status, 429)
          return false
        },
      }),
      error => {
        assert.equal(error instanceof ApplicationRequestError, true)
        assert.equal(error.status, 429)
        return true
      },
    )

    assert.equal(runtimeApp.session.csrfToken, 'fresh-token')
    assert.equal(alerts[0].message, 'too many requests')
    assert.equal(alerts[0].options.title, '请求过于频繁')
    assert.equal(runtimeApp.errors.length, 1)
  } finally {
    console.error = previousConsoleError
  }
})

test('runtime application exposes route helper and resource store adapter', async () => {
  const requests = []
  const resourceStore = createTestResourceStore()
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore,
    router: {
      resolve(location) {
        return {
          href: `/route/${location.name}/${location.params.id}?near=${location.query.near}${location.hash}`,
        }
      },
    },
    api: {
      request(config) {
        requests.push(config)
        return Promise.resolve({
          status: 200,
          data: {
            data: {
              type: 'users',
              id: '2',
              attributes: { username: 'beta' },
            },
          },
        })
      },
    },
  })

  runtimeApp.load({
    api_document: {
      data: {
        type: 'users',
        id: '1',
        attributes: { username: 'alpha' },
      },
    },
  })
  await runtimeApp.boot()

  runtimeApp.preloadedApiDocument()
  const found = await runtimeApp.store.find('users', '2', { include: 'groups' })
  const routeUrl = runtimeApp.route('user', { id: 2, query: { near: 7 }, hash: '#profile' })

  assert.equal(resourceStore.get('users', '1').username, 'alpha')
  assert.equal(resourceStore.get('users', '2').username, 'beta')
  assert.equal(found.username(), 'beta')
  assert.equal(found.payload.data.id, '2')
  assert.equal(requests[0].url, '/users/2')
  assert.deepEqual(requests[0].params, { include: 'groups' })
  assert.equal(routeUrl, '/route/user/2?near=7#profile')
})

test('runtime application resolves registered route definitions and helpers', () => {
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  runtimeApp.routes.definitions['discussion.near'] = {
    path: '/d/:id/:near',
    name: 'discussion.near',
  }
  runtimeApp.routes.helpers.discussion = params => runtimeApp.route('discussion.near', params)
  runtimeApp.route.discussion = runtimeApp.routes.helpers.discussion

  assert.equal(
    runtimeApp.route('discussion.near', { id: 12, near: 5, query: { sort: 'old' }, hash: '#reply' }),
    '/d/12/5?sort=old#reply'
  )
  assert.equal(runtimeApp.route('discussion', { id: 12, near: 5 }), '/d/12/5')
  assert.equal(runtimeApp.route.discussion({ id: 12, near: 5 }), '/d/12/5')
})

test('runtime application store supports extension model registration and relationships', async () => {
  const requests = []
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
    api: {
      request(config) {
        requests.push(config)
        if (config.method === 'delete') {
          return Promise.resolve({
            status: 204,
            data: null,
          })
        }
        return Promise.resolve({
          status: 200,
          data: {
            data: {
              type: 'users',
              id: '1',
              attributes: { username: 'gamma' },
              relationships: {
                bestFriend: { data: { type: 'users', id: '2' } },
                groups: { data: [{ type: 'groups', id: '10' }] },
              },
            },
            included: [
              { type: 'users', id: '2', attributes: { username: 'beta' } },
              { type: 'groups', id: '10', attributes: { name: 'Members' } },
            ],
          },
        })
      },
    },
  })

  await runtimeApp.bootExtensions({
    models: {
      extend: [
        new ModelExtender(UserModel).attribute('username').hasOne('bestFriend').hasMany('groups'),
        new ModelExtender(GroupModel).attribute('name'),
      ],
    },
  })

  const user = runtimeApp.store.pushPayload({
    data: {
      type: 'users',
      id: '1',
      attributes: { username: 'alpha' },
      relationships: {
        bestFriend: { data: { type: 'users', id: '2' } },
        groups: { data: [{ type: 'groups', id: '10' }] },
      },
    },
    included: [
      { type: 'users', id: '2', attributes: { username: 'beta' } },
      { type: 'groups', id: '10', attributes: { name: 'Members' } },
    ],
  })
  const saved = await user.save({ username: 'gamma' })

  assert.equal(user instanceof UserModel, true)
  assert.equal(user.username(), 'gamma')
  assert.equal(user.bestFriend().username(), 'beta')
  assert.equal(user.groups()[0].name(), 'Members')
  assert.equal(runtimeApp.store.getBy('users', 'username', 'gamma'), user)
  assert.equal(saved, user)
  assert.equal(saved.payload.data.attributes.username, 'gamma')
  assert.equal(requests[0].method, 'patch')
  assert.equal(requests[0].url, '/users/1')
  assert.equal(requests[0].data.data.attributes.username, 'gamma')

  await user.delete()
  assert.equal(requests[1].method, 'delete')
  assert.equal(requests[1].url, '/users/1')
  assert.equal(runtimeApp.store.getById('users', '1'), null)
})

test('runtime application registers default resource models', () => {
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
  })

  const discussion = runtimeApp.store.pushPayload({
    data: {
      type: 'discussions',
      id: '10',
      attributes: { title: 'Default models' },
      relationships: {
        user: { data: { type: 'users', id: '1' } },
        posts: { data: [{ type: 'posts', id: '20' }] },
      },
    },
    included: [
      { type: 'users', id: '1', attributes: { username: 'author', display_name: 'Author' } },
      { type: 'posts', id: '20', attributes: { content_html: '<p>Hello</p>' } },
    ],
  })

  assert.equal(discussion.title(), 'Default models')
  assert.equal(discussion.user().displayName(), 'Author')
  assert.equal(discussion.posts()[0].contentHtml(), '<p>Hello</p>')
})

test('store extender registers extension resource models through the runtime app store', async () => {
  class DemoModel extends ResourceModel {
    title() {
      return this.attribute('title')
    }
  }

  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
  })

  await runtimeApp.bootExtensions({
    demo: {
      extend: [
        new Store().add('demo-records', DemoModel),
      ],
    },
  })

  const record = runtimeApp.store.pushPayload({
    data: {
      type: 'demo-records',
      id: '1',
      attributes: { title: 'Registered by extender' },
    },
  })

  assert.equal(record instanceof DemoModel, true)
  assert.equal(record.title(), 'Registered by extender')
  assert.equal(runtimeApp.store.getById('demo-records', '1'), record)
})

test('store extender rejects duplicate extension model registrations', () => {
  class DemoModel extends ResourceModel {}
  class OtherModel extends ResourceModel {}

  assert.throws(
    () => new Store().add('demo-records', DemoModel).add('demo-records', OtherModel),
    /already been registered with this extender/,
  )

  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
  })
  new Store().add('demo-records', DemoModel).extend(runtimeApp)

  assert.throws(
    () => new Store().add('demo-records', OtherModel).extend(runtimeApp),
    /already been registered with the class "DemoModel"/,
  )
})

test('frontend dedicated extenders register notification post search and routes', async () => {
  const notifications = []
  const postTypes = []
  const searchFilters = []
  const themeModes = []
  const forumNavItems = []
  const profilePanels = []
  const searchSources = []
  const heroMetaItems = []
  const userBadges = []
  const pageStates = []
  const discussionListContexts = []
  const discussionListHeroes = []
  const discussionListRequests = []
  const composerSubmitSuccessItems = []
  const forumRealtimeEvents = []
  const dashboardStats = []
  const adminPageCopies = []
  const adminPageConfigs = []
  const adminPageActionMeta = []
  const adminPageNoteTemplates = []
  const adminRoutes = []
  const adminPages = []
  const adminSettings = []
  const adminPermissions = []
  const adminPermissionScopes = []
  const adminSettingOperations = []
  const adminPermissionOperations = []
  const adminRegistryContexts = []
  const generalIndexCalls = []
  const routes = []
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    registry: {
      generalIndex: {
        for(extensionId) {
          generalIndexCalls.push(['for', extensionId])
        },
        add(type, items) {
          generalIndexCalls.push(['add', type, items])
        },
      },
      for(context) {
        adminRegistryContexts.push(context)
      },
      registerNotificationType(definition) {
        notifications.push(definition)
      },
      registerPostType(definition) {
        postTypes.push(definition)
      },
      registerSearchFilter(definition) {
        searchFilters.push(definition)
      },
      registerThemeMode(definition) {
        themeModes.push(definition)
      },
      registerForumNavItem(definition) {
        forumNavItems.push(definition)
      },
      registerProfilePanel(definition) {
        profilePanels.push(definition)
      },
      registerSearchSource(definition) {
        searchSources.push(definition)
      },
      registerHeroMeta(definition) {
        heroMetaItems.push(definition)
      },
      registerUserBadge(definition) {
        userBadges.push(definition)
      },
      registerPageState(definition) {
        pageStates.push(definition)
      },
      registerDiscussionListContext(definition) {
        discussionListContexts.push(definition)
      },
      registerDiscussionListHero(definition) {
        discussionListHeroes.push(definition)
      },
      registerDiscussionListRequest(definition) {
        discussionListRequests.push(definition)
      },
      registerComposerSubmitSuccess(definition) {
        composerSubmitSuccessItems.push(definition)
      },
      registerForumRealtimeEvent(definition) {
        forumRealtimeEvents.push(definition)
      },
      registerAdminDashboardStat(definition) {
        dashboardStats.push(definition)
      },
      registerAdminPageCopy(pageKey, definition) {
        adminPageCopies.push({ pageKey, definition })
      },
      registerAdminPageConfig(pageKey, definition) {
        adminPageConfigs.push({ pageKey, definition })
      },
      registerAdminPageActionMeta(pageKey, definition) {
        adminPageActionMeta.push({ pageKey, definition })
      },
      registerAdminPageNoteTemplate(pageKey, definition) {
        adminPageNoteTemplates.push({ pageKey, definition })
      },
      registerAdminRoute(definition) {
        adminRoutes.push(definition)
      },
      registerPage(definition) {
        adminPages.push(definition)
      },
      registerSetting(definition, priority) {
        adminSettings.push({ definition, priority })
      },
      setSetting(setting, replacement) {
        adminSettingOperations.push(['replace', setting, replacement({ key: setting })])
      },
      setSettingPriority(setting, priority) {
        adminSettingOperations.push(['priority', setting, priority])
      },
      removeSetting(setting) {
        adminSettingOperations.push(['remove', setting])
      },
      registerPermission(definition, type, priority) {
        adminPermissions.push({ definition, type, priority })
      },
      registerAdminPermissionScope(definition) {
        adminPermissionScopes.push(definition)
      },
      setPermission(permission, replacement, type) {
        adminPermissionOperations.push(['replace', permission, type, replacement({ permission })])
      },
      setPermissionPriority(permission, type, priority) {
        adminPermissionOperations.push(['priority', permission, type, priority])
      },
      removePermission(permission, type) {
        adminPermissionOperations.push(['remove', permission, type])
      },
    },
    router: {
      hasRoute() {
        return false
      },
      addRoute(route) {
        routes.push(route)
      },
      resolve(location) {
        return { href: `/resolved/${location.name}/${location.params.id}` }
      },
    },
  })

  await runtimeApp.bootExtensions({
    frontend: {
      extend: [
        new NotificationExtender().add('alphaAlert', { label: 'Alpha alert', component: () => null }),
        new PostTypesExtender().add('gammaEvent', { label: 'Gamma event', component: () => null }),
        new SearchExtender()
          .filter({ key: 'alpha', target: 'discussions', syntax: 'alpha:' })
          .gambit('posts', { key: 'flagged', syntax: 'is:flagged', label: 'Flagged' }),
        new ThemeModeExtender().add('sepia', 'Sepia'),
        new ForumExtender()
          .navItem({ key: 'alpha-nav', label: 'Alpha nav', order: 15 })
          .profilePanel({ key: 'alpha-profile-panel', label: 'Alpha panel', order: 16 })
          .searchSource({ key: 'alpha-search-source', type: 'alpha', label: 'Alpha search', order: 17 })
          .heroMeta({ key: 'alpha-hero-meta', text: 'Alpha meta', order: 18 })
          .userBadge({ key: 'alpha-user-badge', label: 'Alpha badge', order: 19 })
          .discussionListContext({ key: 'alpha-context', order: 20 })
          .discussionListHero({ key: 'alpha-hero', order: 20 })
          .discussionListRequest({ key: 'alpha-request', order: 20 })
          .pageState({ key: 'alpha-page-state', order: 21 })
          .composerSubmitSuccess({ key: 'alpha-composer-success', order: 22 })
          .realtimeEvent({ key: 'alpha-realtime-event', order: 23, eventTypes: ['alpha.event'], refresh: true })
          .postType('alphaEvent', { label: 'Alpha event', component: () => null })
          .postType('betaEvent', { label: 'Beta event', component: () => null }),
        extendAdmin(admin => admin
          .dashboardStat({ key: 'alpha-stat', label: 'Alpha stat', order: 15 })
          .pageCopy('alpha.page', { key: 'alpha-copy', label: 'Alpha copy' })
          .pageConfig('alpha.page', { key: 'alpha-config', value: true })
          .pageActionMeta('alpha.page', { key: 'alpha-action-meta', title: 'Alpha action' })
          .pageNoteTemplate('alpha.page', { key: 'alpha-note', value: 'Alpha note' })),
        new RoutesExtender()
          .add('alpha.page', '/alpha', () => null, { meta: { title: 'Alpha' } })
          .helper('alphaUser', (app, id) => app.route('user', { id })),
        new ExportsExtender().module('toolbox', { ready: true }),
        new AdminExtender().page({
          name: 'admin.alpha',
          path: '/admin/alpha',
          component: () => null,
          label: 'Alpha',
        })
          .setting(() => ({ key: 'alpha_setting' }), 10)
          .replaceSetting('alpha_setting', original => ({ ...original, replaced: true }))
          .setSettingPriority('alpha_setting', 20)
          .removeSetting('old_setting')
          .permission(() => ({ permission: 'alpha.use' }), 'moderate', 30)
          .permissionScope({ key: 'alpha-scope', label: 'Alpha scope' })
          .replacePermission('alpha.use', original => ({ ...original, replaced: true }), 'moderate')
          .setPermissionPriority('alpha.use', 'moderate', 40)
          .removePermission('old.use', 'moderate')
          .generalIndexItems('settings', () => [{ label: 'Alpha setting' }]),
      ],
    },
  })

  assert.equal(adminRoutes[0].path, '/admin/alpha')
  assert.equal(adminRoutes[0].extensionId, 'frontend')
  assert.deepEqual(adminSettings, [])

  await runtimeApp.runBeforeMount()

  assert.equal(notifications[0].type, 'alphaAlert')
  assert.equal(postTypes[0].type, 'gammaEvent')
  assert.equal(postTypes[1].type, 'alphaEvent')
  assert.equal(postTypes[2].type, 'betaEvent')
  assert.equal(postTypes[0].extensionId, 'frontend')
  assert.equal(runtimeApp.notificationComponents.alphaAlert, notifications[0].component)
  assert.equal(runtimeApp.postComponents.gammaEvent, postTypes[0].component)
  assert.equal(runtimeApp.postComponents.alphaEvent, postTypes[1].component)
  assert.equal(runtimeApp.postComponents.betaEvent, postTypes[2].component)
  assert.equal(searchFilters.some(item => item.key === 'alpha'), true)
  assert.equal(searchFilters.some(item => item.key === 'flagged'), true)
  assert.deepEqual(runtimeApp.search.gambits.gambits.posts, [{ key: 'flagged', syntax: 'is:flagged', label: 'Flagged' }])
  assert.deepEqual(themeModes[0], { id: 'sepia', mode: 'sepia', label: 'Sepia' })
  assert.equal(forumNavItems[0].key, 'alpha-nav')
  assert.equal(forumNavItems[0].extensionId, 'frontend')
  assert.equal(profilePanels[0].key, 'alpha-profile-panel')
  assert.equal(profilePanels[0].extensionId, 'frontend')
  assert.equal(searchSources[0].key, 'alpha-search-source')
  assert.equal(searchSources[0].extensionId, 'frontend')
  assert.equal(heroMetaItems[0].key, 'alpha-hero-meta')
  assert.equal(heroMetaItems[0].extensionId, 'frontend')
  assert.equal(userBadges[0].key, 'alpha-user-badge')
  assert.equal(userBadges[0].extensionId, 'frontend')
  assert.equal(discussionListContexts[0].key, 'alpha-context')
  assert.equal(discussionListContexts[0].extensionId, 'frontend')
  assert.equal(discussionListHeroes[0].key, 'alpha-hero')
  assert.equal(discussionListHeroes[0].extensionId, 'frontend')
  assert.equal(discussionListRequests[0].key, 'alpha-request')
  assert.equal(discussionListRequests[0].extensionId, 'frontend')
  assert.equal(pageStates[0].key, 'alpha-page-state')
  assert.equal(pageStates[0].extensionId, 'frontend')
  assert.equal(composerSubmitSuccessItems[0].key, 'alpha-composer-success')
  assert.equal(composerSubmitSuccessItems[0].extensionId, 'frontend')
  assert.equal(forumRealtimeEvents[0].key, 'alpha-realtime-event')
  assert.equal(forumRealtimeEvents[0].extensionId, 'frontend')
  assert.equal(dashboardStats[0].key, 'alpha-stat')
  assert.equal(dashboardStats[0].moduleId, 'frontend')
  assert.deepEqual(adminPageCopies[0], {
    pageKey: 'alpha.page',
    definition: {
      key: 'alpha-copy',
      label: 'Alpha copy',
      extensionId: 'frontend',
      extension_id: 'frontend',
      moduleId: 'frontend',
      module_id: 'frontend',
    },
  })
  assert.equal(adminPageConfigs[0].definition.key, 'alpha-config')
  assert.equal(adminPageConfigs[0].definition.extensionId, 'frontend')
  assert.equal(adminPageActionMeta[0].definition.key, 'alpha-action-meta')
  assert.equal(adminPageActionMeta[0].definition.extensionId, 'frontend')
  assert.equal(adminPageNoteTemplates[0].definition.key, 'alpha-note')
  assert.equal(adminPageNoteTemplates[0].definition.extensionId, 'frontend')
  assert.equal(runtimeApp.themeModes[0].id, 'sepia')
  assert.equal(routes[0].name, 'alpha.page')
  assert.equal(runtimeApp.routes.definitions['alpha.page'].path, '/alpha')
  assert.equal(runtimeApp.route.alphaUser(7), '/resolved/user/7')
  assert.deepEqual(runtimeApp.exportRegistry.get('frontend', 'toolbox'), { ready: true })
  assert.deepEqual(adminRegistryContexts, ['frontend', 'frontend', 'frontend', 'frontend'])
  assert.equal(adminPages[0].path, '/admin/alpha')
  assert.equal(adminPages[0].extensionId, 'frontend')
  assert.deepEqual(adminSettings[0], { definition: { key: 'alpha_setting' }, priority: 10 })
  assert.deepEqual(adminSettingOperations, [
    ['replace', 'alpha_setting', { key: 'alpha_setting', replaced: true }],
    ['priority', 'alpha_setting', 20],
    ['remove', 'old_setting'],
  ])
  assert.deepEqual(adminPermissions[0], { definition: { permission: 'alpha.use' }, type: 'moderate', priority: 30 })
  assert.equal(adminPermissionScopes[0].key, 'alpha-scope')
  assert.equal(adminPermissionScopes[0].extensionId, 'frontend')
  assert.deepEqual(adminPermissionOperations, [
    ['replace', 'alpha.use', 'moderate', { permission: 'alpha.use', replaced: true }],
    ['priority', 'alpha.use', 'moderate', 40],
    ['remove', 'old.use', 'moderate'],
  ])
  assert.deepEqual(generalIndexCalls, [
    ['for', 'frontend'],
    ['add', 'settings', [{ label: 'Alpha setting' }]],
  ])
})

test('common extenders export unified frontend extension entry', () => {
  assert.equal(extenders.Model, ModelExtender)
  assert.equal(extenders.Store, StoreExtender)
  assert.equal(extenders.PostTypes, PostTypesExtender)
  assert.equal(extenders.Search, SearchExtender)
  assert.equal(extenders.ThemeMode, ThemeModeExtender)
  assert.equal(extenders.AdminExtender, AdminExtender)
  assert.equal(extenders.Exports, ExportsExtender)
  assert.equal(extenders.ForumExtender, ForumExtender)
  assert.equal(extenders.extendAdmin, extendAdmin)
  assert.equal(extenders.extendForum, extendForum)
  assert.equal(new Model(UserModel) instanceof ModelExtender, true)
  assert.equal(new ResourceModelExtender(UserModel) instanceof ModelExtender, true)
  assert.equal(new Store().add('users', UserModel) instanceof StoreExtender, true)
  assert.equal(new PostTypes().add('demo-alias', { label: 'Demo alias' }) instanceof PostTypesExtender, true)
  assert.equal(new PostTypesExtender().add('demo', { label: 'Demo' }) instanceof PostTypesExtender, true)
  assert.equal(new Search().gambit('users', query => query) instanceof SearchExtender, true)
  assert.equal(new ThemeMode().add('dark', 'Dark') instanceof ThemeModeExtender, true)
  assert.equal(extendAdmin(admin => admin.page({ path: '/admin/demo' })) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().setting({ key: 'demo_setting' }) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().customSetting({ key: 'demo_custom_setting' }) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().replaceSetting('demo_setting', setting => setting) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().setSettingPriority('demo_setting', 10) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().removeSetting('demo_setting') instanceof AdminExtender, true)
  assert.equal(new AdminExtender().permission({ permission: 'demo.use' }) instanceof AdminExtender, true)
  assert.equal(extendAdmin(admin => admin.permissionScope({ key: 'demo' })) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().replacePermission('demo.use', permission => permission) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().setPermissionPriority('demo.use', 'moderate', 10) instanceof AdminExtender, true)
  assert.equal(new AdminExtender().removePermission('demo.use') instanceof AdminExtender, true)
  assert.equal(new AdminExtender().generalIndexItems('settings', [{ key: 'demo' }]) instanceof AdminExtender, true)
  assert.equal(extendAdmin(admin => admin.dashboardStat({ key: 'demo' })) instanceof AdminExtender, true)
  assert.equal(extendAdmin(admin => admin.pageCopy('demo.page', { key: 'demo' })) instanceof AdminExtender, true)
  assert.equal(new Exports().module('demo', {}) instanceof ExportsExtender, true)
  assert.equal(new ForumExtender().navItem({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().profilePanel({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().searchSource({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().heroMeta({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().userBadge({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().discussionListContext({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().discussionListHero({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().discussionListRequest({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().pageState({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().composerSubmitSuccess({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().realtimeEvent({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().postType('demo', { label: 'Demo' }) instanceof ForumExtender, true)
  assert.equal(new ForumExtender().feedbackNote({ key: 'demo' }) instanceof ForumExtender, true)
  assert.equal(extendForum(forum => forum.navItem({ key: 'demo' })) instanceof ForumExtender, true)
  const scopedForum = extendForum('demo-extension', forum => forum.navItem({ key: 'scoped-demo' }))
  assert.equal(scopedForum instanceof ForumExtender, true)
  assert.equal(scopedForum.context, 'demo-extension')
})

test('callback extenders run during extension boot instead of module evaluation', async () => {
  const forumNavItems = []
  const adminRoutes = []
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    registry: {
      registerForumNavItem(item) {
        forumNavItems.push(item)
      },
      registerAdminRoute(route) {
        adminRoutes.push(route)
      },
      registerPage(route) {
        adminRoutes.push(route)
      },
    },
  })

  const forumExtender = extendForum('lazy-forum', forum => forum.navItem({
    key: forumNavKey,
    label: 'Lazy forum',
  }))
  const adminExtender = extendAdmin('lazy-admin', admin => admin.route({
    name: adminRouteName,
    path: '/admin/lazy',
  }))
  const forumNavKey = 'lazy-nav'
  const adminRouteName = 'lazy-admin-route'

  assert.deepEqual(forumExtender.items, [])
  assert.deepEqual(adminExtender.routes, [])

  await runtimeApp.bootExtensions({
    forumLazy: { extend: [forumExtender] },
    adminLazy: { extend: [adminExtender] },
  })
  await runtimeApp.runBeforeMount()

  assert.equal(forumNavItems[0].key, forumNavKey)
  assert.equal(forumNavItems[0].extensionId, 'forumLazy')
  assert.equal(adminRoutes.some(route => route.name === adminRouteName), true)
})

test('approval extension owns pending composer submit alerts', async () => {
  const {
    registerApprovalComposerCopy,
    registerApprovalComposerSubmitSuccess,
  } = await import('../../../extensions/approval/frontend/forum/approvalComposer.js')
  const composerSubmitSuccessHandlers = []
  const copyItems = []
  const forum = {
    composerSubmitSuccess(definition) {
      composerSubmitSuccessHandlers.push(definition)
      return this
    },
    uiCopy(definition) {
      copyItems.push(definition)
      return this
    },
  }

  registerApprovalComposerCopy(forum)
  registerApprovalComposerSubmitSuccess(forum)

  const handler = composerSubmitSuccessHandlers.find(item => item.key === 'approval-pending-submit-alert')
  assert.equal(handler.moduleId, 'approval')
  assert.equal(copyItems.find(item => item.key === 'discussion-event-approved-label').moduleId, 'approval')
  assert.equal(copyItems.find(item => item.key === 'post-event-approved-label').resolve({ targetPostNumber: 3 }).text, '通过了第 3 楼回复的审核')
  assert.equal(handler.isVisible({
    type: 'discussion',
    mode: 'create',
    data: { approval_status: 'pending' },
  }), true)
  assert.equal(handler.isVisible({
    type: 'discussion',
    mode: 'create',
    data: { approval_status: 'approved' },
  }), false)

  const alerts = []
  await handler.run({
    type: 'post',
    mode: 'reply',
    post: { approval_status: 'pending' },
    modalStore: {
      alert(payload) {
        alerts.push(payload)
      },
    },
  })

  assert.deepEqual(alerts, [{
    title: '回复已进入审核队列',
    message: '管理员通过后，这条回复才会显示给其他用户。',
  }])
})

test('approval extension owns moderation action handlers', async () => {
  const { api } = await import('@bias/core')
  const { registerApprovalModerationActions } = await import('../../../extensions/approval/frontend/forum/approvalModerationActions.js')
  const originalPost = api.post
  const discussionHandlers = []
  const postHandlers = []
  const copyItems = []
  const requests = []
  const alerts = []
  const refreshes = []
  const forum = {
    discussionActionHandler(definition) {
      discussionHandlers.push(definition)
      return this
    },
    postActionHandler(definition) {
      postHandlers.push(definition)
      return this
    },
    uiCopy(definition) {
      copyItems.push(definition)
      return this
    },
  }

  try {
    api.post = async (url, payload) => {
      requests.push([url, payload])
      return { data: { ok: true } }
    }

    registerApprovalModerationActions(forum)

    assert.deepEqual(discussionHandlers.map(item => item.key), ['approve', 'reject'])
    assert.deepEqual(postHandlers.map(item => item.key), ['approve', 'reject'])
    assert.equal(copyItems.find(item => item.key === 'discussion-detail-moderation-title').moduleId, 'approval')

    await discussionHandlers[0].resolve().handle({
      discussion: { id: 7, approval_status: 'pending' },
      modalStore: {
        async show(_component, props) {
          await props.submitAction({ note: 'ok' })
          return { success: true }
        },
        async alert(payload) {
          alerts.push(payload)
        },
      },
      refreshDiscussion() {
        refreshes.push('discussion')
      },
    })

    await postHandlers[1].resolve().handle({
      post: { id: 9, number: 4, approval_status: 'pending' },
      modalStore: {
        async show(_component, props) {
          await props.submitAction({ note: 'no' })
          return { success: true }
        },
        async alert(payload) {
          alerts.push(payload)
        },
      },
      refreshDiscussion() {
        refreshes.push('post')
      },
    })

    assert.deepEqual(requests, [
      ['/admin/approval-queue/discussion/7/approve', { note: 'ok' }],
      ['/admin/approval-queue/post/9/reject', { note: 'no' }],
    ])
    assert.deepEqual(refreshes, ['discussion', 'post'])
    assert.equal(alerts.length, 2)
  } finally {
    api.post = originalPost
  }
})

test('search gambits transform store find filter queries', async () => {
  const requests = []
  const runtimeApp = createRuntimeApplication({
    kind: 'forum',
    resourceStore: createTestResourceStore(),
    api: {
      request(config) {
        requests.push(config)
        return Promise.resolve({
          status: 200,
          data: {
            data: [],
          },
        })
      },
    },
  })

  await runtimeApp.bootExtensions({
    search: {
      extend: [
        new SearchExtender().gambit('users', (query) => `${query} is:active`.trim()),
      ],
    },
  })

  await runtimeApp.store.find('users', { filter: { q: 'alice' } })

  assert.equal(requests[0].params.filter.q, 'alice is:active')
})

test('loadEnabledForumExtensions runs initializers after all entries load', async () => {
  const calls = []

  await loadEnabledForumExtensions({
    fetchPayload: async () => ({
      enabled_extensions: [
        {
          id: 'first',
          frontend_forum_entry: 'extensions/first/frontend/forum/index.js',
        },
        {
          id: 'second',
          frontend_forum_entry: 'extensions/second/frontend/forum/index.js',
        },
      ],
    }),
    importers: {
      '../../../extensions/first/frontend/forum/index.js': async () => ({
        extend: [{
          extend(app) {
          calls.push('first:extend')
          app.initializers.add('first', () => calls.push('first:init'))
          },
        }],
      }),
      '../../../extensions/second/frontend/forum/index.js': async () => ({
        extend: [{
          extend(app) {
          calls.push('second:extend')
          app.initializers.add('second', () => calls.push('second:init'))
          },
        }],
      }),
    },
  })

  assert.deepEqual(calls, ['first:extend', 'second:extend', 'first:init', 'second:init'])
})

test('loadEnabledForumExtensions isolates failing entry modules and continues booting routes', async () => {
  clearExtensionRuntimeErrors()
  const routes = []
  const router = {
    addRoute(route) {
      routes.push(route)
    },
    hasRoute() {
      return false
    },
  }
  const calls = []

  const result = await loadEnabledForumExtensions({
    router,
    fetchPayload: async () => ({
      enabled_extensions: [
        {
          id: 'broken',
          frontend_forum_entry: 'extensions/broken/frontend/forum/index.js',
        },
        {
          id: 'discussions',
          frontend_forum_entry: 'extensions/discussions/frontend/forum/index.js',
          frontend_routes: [{
            name: 'home',
            path: '/',
            component: './DiscussionListView.vue',
            frontend: 'forum',
          }],
        },
      ],
    }),
    importers: {
      '../../../extensions/broken/frontend/forum/index.js': async () => {
        throw new Error('broken entry')
      },
      '../../../extensions/discussions/frontend/forum/index.js': async () => {
        calls.push('discussions')
        return { extend: [] }
      },
      'discussions:./DiscussionListView.vue': async () => ({ default: { name: 'DiscussionListView' } }),
    },
  })

  assert.equal(result.extensionErrors.length, 1)
  assert.equal(result.extensionErrors[0].extensionId, 'broken')
  assert.equal(result.loadedExtensionIds.has('broken'), false)
  assert.equal(result.loadedExtensionIds.has('discussions'), true)
  assert.deepEqual(calls, ['discussions'])
  assert.equal(routes.length, 1)
  assert.equal(routes[0].name, 'home')
  assert.equal(getExtensionRuntimeErrors().some(item => item.extensionId === 'broken' && item.operation === 'forum-entry'), true)
  clearExtensionRuntimeErrors()
})

test('extension runtime supports lazy module patching and error dedupe', () => {
  clearExtensionRuntimeErrors()
  class LazyTarget {
    items() {
      return []
    }
  }

  extendMethod('lazy-target', 'items', items => items.push('lazy'), { extensionId: 'lazy-extension' })
  registerLazyExtensionModule('lazy-target', LazyTarget)

  assert.deepEqual(new LazyTarget().items(), ['lazy'])

  extendMethod(LazyTarget.prototype, 'items', () => {
    throw new Error('same failure')
  }, { extensionId: 'lazy-extension' })
  new LazyTarget().items()
  new LazyTarget().items()
  assert.equal(getExtensionRuntimeErrors().filter(item => item.message === 'same failure').length, 1)
  clearExtensionRuntimeErrors('lazy-extension')
  assert.equal(getExtensionRuntimeErrors().length, 0)
})

test('resetForumExtensionRuntimeContributions cancels pending lazy patches', () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }

  try {
    class PendingTarget {
      items() {
        return []
      }
    }

    extendMethod('pending-target', 'items', items => items.push('pending'), { extensionId: 'pending-extension' })
    resetForumExtensionRuntimeContributions('pending-extension')
    registerLazyExtensionModule('pending-target', PendingTarget)

    assert.deepEqual(new PendingTarget().items(), [])
  } finally {
    globalThis.bias = previousBias
  }
})

test('resetForumExtensionRuntimeContributions clears loaded lazy modules by owner', () => {
  const previousBias = globalThis.bias
  globalThis.bias = { extensions: Object.create(null) }

  try {
    const ownedModule = { name: 'owned-lazy' }
    const pathModule = { name: 'path-lazy' }
    const calls = []

    registerLazyExtensionModule('shared-lazy-key', ownedModule, { extensionId: 'lazy-owner' })
    registerLazyExtensionModule('extensions/path-owner/frontend/forum/lazy.js', pathModule)
    resetForumExtensionRuntimeContributions('lazy-owner')
    resetForumExtensionRuntimeContributions('path-owner')

    onLazyModuleLoad('shared-lazy-key', loaded => calls.push(loaded))
    onLazyModuleLoad('extensions/path-owner/frontend/forum/lazy.js', loaded => calls.push(loaded))

    assert.equal(globalThis.bias.reg.getModule('shared-lazy-key'), null)
    assert.equal(globalThis.bias.reg.getModule('extensions/path-owner/frontend/forum/lazy.js'), null)
    assert.deepEqual(calls, [])
  } finally {
    globalThis.bias = previousBias
  }
})

test('resetForumExtensionRuntimeContributions removes scoped registry items', () => {
  registerForumNavItem({
    key: 'manual-core',
    label: 'Core',
  })
  registerForumNavItem({
    key: 'manual-extension',
    label: 'Extension',
    extensionId: 'scoped',
  })

  assert.equal(getForumNavItems().some(item => item.key === 'manual-extension'), true)
  resetForumExtensionRuntimeContributions('scoped')
  assert.equal(getForumNavItems().some(item => item.key === 'manual-extension'), false)
  assert.equal(getForumNavItems().some(item => item.key === 'manual-core'), true)
})

test('registerExtensionForumRoutes registers declarative forum routes', () => {
  const routes = []
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  const router = {
    existing: new Set(),
    hasRoute(name) {
      return this.existing.has(name)
    },
    addRoute(route) {
      this.existing.add(route.name)
      routes.push(route)
    },
  }

  const registered = registerExtensionForumRoutes(router, {
    id: 'route-demo',
    frontend_routes: [
      {
        path: '/route-demo',
        name: 'route-demo',
        component: 'RouteDemoView',
        frontend: 'forum',
        module_id: 'route-demo',
        title: 'Route demo',
      },
      {
        path: '/admin/route-demo',
        name: 'admin-route-demo',
        component: 'RouteDemoView',
        frontend: 'admin',
      },
    ],
  }, {
    app: runtimeApp,
    components: {
      RouteDemoView: async () => ({ default: 'RouteDemoView' }),
    },
  })

  assert.deepEqual(registered, ['route-demo'])
  assert.equal(routes.length, 1)
  assert.equal(routes[0].meta.extensionId, 'route-demo')
  assert.equal(routes[0].meta.moduleId, 'route-demo')
  assert.equal(runtimeApp.routes.definitions['route-demo'].path, '/route-demo')
  assert.equal(runtimeApp.routes.definitions['route-demo'].moduleId, 'route-demo')
  assert.equal(runtimeApp.routes.definitions['route-demo'].title, 'Route demo')
})

test('registerExtensionForumRoutes resolves extension-owned route components from generated importers', async () => {
  const routes = []
  const router = {
    existing: new Set(),
    hasRoute(name) {
      return this.existing.has(name)
    },
    addRoute(route) {
      this.existing.add(route.name)
      routes.push(route)
    },
  }
  const loadedComponent = { name: 'RouteDemoPage' }
  const extension = {
    id: 'route-demo',
    frontend_forum_entry: 'extensions/route-demo/frontend/forum/index.js',
    frontend_routes: [{
      path: '/route-demo',
      name: 'route-demo.page',
      component: './Page.vue',
      frontend: 'forum',
    }],
  }

  const registered = registerExtensionForumRoutes(router, extension, {
    importers: {
      'route-demo:./Page.vue': async () => ({ default: loadedComponent }),
    },
  })

  assert.deepEqual(registered, ['route-demo.page'])
  assert.deepEqual(resolveForumRouteComponentKeys('./Page.vue', extension), [
    'route-demo:./Page.vue',
    'route-demo:extensions/route-demo/frontend/forum/Page.vue',
    'extensions/route-demo/frontend/forum/Page.vue',
    '../../../extensions/route-demo/frontend/forum/Page.vue',
    './Page.vue',
  ])
  assert.equal(await routes[0].component(), loadedComponent)
})

test('registerExtensionForumRoutes removes declared forum routes', () => {
  const removed = []
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  runtimeApp.routes.definitions['route-demo'] = {
    path: '/route-demo',
    name: 'route-demo',
  }
  const router = {
    existing: new Set(['route-demo']),
    hasRoute(name) {
      return this.existing.has(name)
    },
    removeRoute(name) {
      this.existing.delete(name)
      removed.push(name)
    },
    addRoute() {
      throw new Error('should not add removed route')
    },
  }

  const registered = registerExtensionForumRoutes(router, {
    id: 'route-demo',
    frontend_routes: [
      {
        name: 'route-demo',
        frontend: 'forum',
        removed: true,
      },
    ],
  }, { app: runtimeApp })

  assert.deepEqual(registered, ['route-demo'])
  assert.deepEqual(removed, ['route-demo'])
  assert.equal(runtimeApp.routes.definitions['route-demo'], undefined)
})

test('resetLoadedExtensionsWhenRuntimeChanges clears loaded ids on stamp change', () => {
  const loadedIds = new Set(['alpha'])

  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), true)
  assert.equal(loadedIds.has('alpha'), true)
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), false)
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'two' }), true)
  assert.equal(loadedIds.size, 0)
})

test('loadEnabledForumExtensions registers route-only extensions', async () => {
  const routes = []
  const payload = {
    enabled_extensions: [
      {
        id: 'route-demo',
        frontend_routes: [
          {
            path: '/route-demo',
            name: 'route-demo',
            component: 'RouteDemoView',
            frontend: 'forum',
          },
        ],
      },
    ],
  }

  const result = await loadEnabledForumExtensions({
    fetchPayload: async () => payload,
    router: {
      hasRoute() {
        return false
      },
      addRoute(route) {
        routes.push(route)
      },
    },
    routeComponents: {
      RouteDemoView: async () => ({ default: 'RouteDemoView' }),
    },
  })

  assert.equal(routes.length, 1)
  assert.equal(result.loadedExtensionIds.has('route-demo'), true)
})

test('loadEnabledForumExtensions resolves route-only components from frontend outputs', async () => {
  const runtimeApp = createRuntimeApplication({ kind: 'forum' })
  const routes = []
  const component = { name: 'RouteOnlyPage' }

  const result = await loadEnabledForumExtensions({
    app: runtimeApp,
    fetchPayload: async () => ({
      enabled_extensions: [{
        id: 'route-output',
        frontend_outputs: {
          forum: {
            revision: 'rev-route',
            chunks: [{
              file: 'assets/route-output-page.js',
              module_id: 'frontend/forum/Page.vue',
            }],
          },
        },
        frontend_routes: [{
          path: '/route-output',
          name: 'route-output.page',
          component: './Page.vue',
          frontend: 'forum',
        }],
      }],
    }),
    router: {
      hasRoute() {
        return false
      },
      addRoute(route) {
        routes.push(route)
      },
    },
    importers: {},
  })

  runtimeApp.exportRegistry.registerChunk('route-output', 'forum/assets/route-output-page.js', {
    'frontend/forum/Page.vue': async () => ({ default: component }),
  })

  assert.equal(result.loadedExtensionIds.has('route-output'), true)
  assert.equal(routes.length, 1)
  assert.equal(await routes[0].component(), component)
})
