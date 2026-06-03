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
  resetForumExtensionRuntimeContributions,
  resetLoadedExtensionsWhenRuntimeChanges,
  validateForumExtensionModule,
} from './extensionLoader.js'
import { getForumNavItems, registerForumNavItem } from './frontendRegistry.js'
import {
  clearExtensionRuntimeErrors,
  extendMethod,
  getExtensionRuntimeErrors,
  registerLazyExtensionModule,
} from '../common/extensionRuntime.js'

test('normalizeExtensionForumEntry rewrites extension paths', () => {
  assert.equal(
    normalizeExtensionForumEntry('extensions/sample-hello/frontend/forum/index.js'),
    '../../../extensions/sample-hello/frontend/forum/index.js',
  )
  assert.equal(normalizeExtensionForumEntry(''), '')
})

test('loadExtensionForumEntryModule loads filesystem importer entries', async () => {
  const loaded = await loadExtensionForumEntryModule('../../../extensions/sample-hello/frontend/forum/index.js', {
    importers: {
      '../../../extensions/sample-hello/frontend/forum/index.js': async () => ({
        boot: true,
      }),
    },
  })

  assert.equal(loaded.boot, true)
})

test('validateForumExtensionModule rejects modules without bootForumExtension', () => {
  assert.throws(
    () => validateForumExtensionModule({}),
    /bootForumExtension/,
  )
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
        id: 'emoji',
        frontend_forum_entry: 'extensions/emoji/frontend/forum/index.js',
      },
      {
        id: 'emoji',
        frontend_forum_entry: 'extensions/emoji/frontend/forum/index.js',
      },
    ],
    extension_document: {
      preloads: ['/assets/emoji.css'],
    },
  }

  const result = await loadEnabledForumExtensions({
    forumStore,
    fetchPayload: async () => payload,
    importers: {
      '../../../extensions/emoji/frontend/forum/index.js': async () => {
        calls.push('emoji')
        return {
          bootForumExtension: async ({ extension }) => {
            calls.push(extension.id)
          },
        }
      },
    },
  })

  assert.equal(calls.length, 2)
  assert.equal(result.loadedExtensionIds.has('emoji'), true)
  assert.equal(forumStore.applied, payload)
  assert.deepEqual(result.extensionDocument.preloads, ['/assets/emoji.css'])
})

test('loadEnabledForumExtensions passes public extension app object', async () => {
  let receivedApp = null
  const extension = {
    id: 'emoji',
    frontend_forum_entry: 'extensions/emoji/frontend/forum/index.js',
  }

  await loadEnabledForumExtensions({
    fetchPayload: async () => ({ enabled_extensions: [extension] }),
    registry: {
      registerForumNavItem() {},
    },
    importers: {
      '../../../extensions/emoji/frontend/forum/index.js': async () => ({
        bootForumExtension: async ({ app, api, registry, documentRuntime }) => {
          receivedApp = app
          assert.equal(api, app.api)
          assert.equal(registry, app.registry)
          assert.equal(documentRuntime, app.documentRuntime)
        },
      }),
    },
  })

  assert.equal(receivedApp.extension, extension)
  assert.equal(typeof receivedApp.registry.registerForumNavItem, 'function')
  assert.equal(typeof receivedApp.documentRuntime.registerContent, 'function')
  assert.equal(typeof receivedApp.initializers.add, 'function')
  assert.equal(typeof receivedApp.extend, 'function')
  assert.equal(typeof receivedApp.override, 'function')
  assert.equal(typeof receivedApp.cache, 'object')
  assert.equal(typeof receivedApp.alerts.success, 'function')
  assert.equal(typeof receivedApp.translator.trans, 'function')
  assert.equal(typeof receivedApp.errors.report, 'function')
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
        bootForumExtension: async ({ app }) => {
          app.initializers.add('scoped', () => {
            app.extend(target, 'items', (items) => {
              items.push('extended')
            })
            calls.push('initializer')
          })
        },
      }),
    },
  })

  assert.deepEqual(calls, ['initializer'])
  assert.deepEqual(target.items(), ['extended'])
  assert.equal(getForumInitializers().list().length, 0)
  resetForumExtensionRuntimeContributions('scoped')
  assert.deepEqual(target.items(), [])
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
        bootForumExtension: async ({ app }) => {
          calls.push('first:boot')
          app.initializers.add('first', () => calls.push('first:init'))
        },
      }),
      '../../../extensions/second/frontend/forum/index.js': async () => ({
        bootForumExtension: async ({ app }) => {
          calls.push('second:boot')
          app.initializers.add('second', () => calls.push('second:init'))
        },
      }),
    },
  })

  assert.deepEqual(calls, ['first:boot', 'second:boot', 'first:init', 'second:init'])
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
    id: 'tags',
    frontend_routes: [
      {
        path: '/tags',
        name: 'tags',
        component: 'TagsView',
        frontend: 'forum',
        module_id: 'tags',
        title: '全部标签',
      },
      {
        path: '/admin/tags',
        name: 'admin-tags',
        component: 'TagsView',
        frontend: 'admin',
      },
    ],
  }, {
    components: {
      TagsView: async () => ({ default: 'TagsView' }),
    },
  })

  assert.deepEqual(registered, ['tags'])
  assert.equal(routes.length, 1)
  assert.equal(routes[0].meta.extensionId, 'tags')
  assert.equal(routes[0].meta.moduleId, 'tags')
})

test('registerExtensionForumRoutes removes declared forum routes', () => {
  const removed = []
  const router = {
    existing: new Set(['tags']),
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
    id: 'tags',
    frontend_routes: [
      {
        name: 'tags',
        frontend: 'forum',
        removed: true,
      },
    ],
  })

  assert.deepEqual(registered, ['tags'])
  assert.deepEqual(removed, ['tags'])
})

test('resetLoadedExtensionsWhenRuntimeChanges clears loaded ids on stamp change', () => {
  const loadedIds = new Set(['emoji'])

  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), true)
  assert.equal(loadedIds.has('emoji'), true)
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'one' }), false)
  assert.equal(resetLoadedExtensionsWhenRuntimeChanges(loadedIds, { stamp: 'two' }), true)
  assert.equal(loadedIds.size, 0)
})

test('loadEnabledForumExtensions registers route-only extensions', async () => {
  const routes = []
  const payload = {
    enabled_extensions: [
      {
        id: 'tags',
        frontend_routes: [
          {
            path: '/tags',
            name: 'tags',
            component: 'TagsView',
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
      TagsView: async () => ({ default: 'TagsView' }),
    },
  })

  assert.equal(routes.length, 1)
  assert.equal(result.loadedExtensionIds.has('tags'), true)
})
