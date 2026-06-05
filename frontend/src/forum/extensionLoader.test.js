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
import { ApplicationRequestError, createRuntimeApplication } from '../common/application.js'
import { ModelExtender } from '../common/resourceModel.js'
import extenders, { Admin, Model, Search, ThemeMode } from '../common/extenders.js'
import {
  AdminExtender,
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
          bootForumExtension: async ({ extension }) => {
            calls.push(extension.id)
          },
        }
      },
    },
  })

  assert.equal(calls.length, 2)
  assert.equal(result.loadedExtensionIds.has('alpha'), true)
  assert.equal(forumStore.applied, payload)
  assert.deepEqual(result.extensionDocument.preloads, ['/assets/alpha.css'])
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

  try {
    await loadEnabledForumExtensions({
      app: runtimeApp,
      fetchPayload: async () => ({ enabled_extensions: [extension] }),
      registry: {
        registerForumNavItem() {},
      },
      importers: {
        '../../../extensions/alpha/frontend/forum/index.js': async () => ({
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
    assert.equal(receivedApp.route, runtimeApp.route)
    assert.equal(receivedApp.routes, runtimeApp.routes)
    assert.equal(receivedApp.search, runtimeApp.search)
    assert.equal(receivedApp.notificationComponents, runtimeApp.notificationComponents)
    assert.equal(receivedApp.postComponents, runtimeApp.postComponents)
    assert.equal(runtimeApp.extensions.alpha.modules.forum.bootForumExtension instanceof Function, true)
    assert.equal(globalThis.bias.extensions.alpha, runtimeApp.extensions.alpha)
  } finally {
    globalThis.bias = previousBias
  }
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
        bootForumExtension: async ({ app }) => {
          assert.equal(app.initializers, runtimeApp.initializers)
          app.initializers.add('runtime-scoped', extensionApp => {
            calls.push(extensionApp.extension.id)
          })
        },
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

test('frontend dedicated extenders register notification post search and routes', async () => {
  const notifications = []
  const postTypes = []
  const searchFilters = []
  const themeModes = []
  const adminRoutes = []
  const adminPages = []
  const adminSettings = []
  const adminPermissions = []
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
        new PostTypesExtender().add('alphaEvent', { label: 'Alpha event', component: () => null }),
        new SearchExtender()
          .filter({ key: 'alpha', target: 'discussions', syntax: 'alpha:' })
          .gambit('posts', { key: 'flagged', syntax: 'is:flagged', label: 'Flagged' }),
        new ThemeModeExtender().add('sepia', 'Sepia'),
        new RoutesExtender()
          .add('alpha.page', '/alpha', () => null, { meta: { title: 'Alpha' } })
          .helper('alphaUser', (app, id) => app.route('user', { id })),
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
  assert.equal(postTypes[0].type, 'alphaEvent')
  assert.equal(runtimeApp.notificationComponents.alphaAlert, notifications[0].component)
  assert.equal(runtimeApp.postComponents.alphaEvent, postTypes[0].component)
  assert.equal(searchFilters.some(item => item.key === 'alpha'), true)
  assert.equal(searchFilters.some(item => item.key === 'flagged'), true)
  assert.deepEqual(runtimeApp.search.gambits.gambits.posts, [{ key: 'flagged', syntax: 'is:flagged', label: 'Flagged' }])
  assert.deepEqual(themeModes[0], { id: 'sepia', mode: 'sepia', label: 'Sepia' })
  assert.equal(runtimeApp.themeModes[0].id, 'sepia')
  assert.equal(routes[0].name, 'alpha.page')
  assert.equal(runtimeApp.routes.definitions['alpha.page'].path, '/alpha')
  assert.equal(runtimeApp.route.alphaUser(7), '/resolved/user/7')
  assert.deepEqual(adminRegistryContexts, ['frontend'])
  assert.equal(adminPages[0].path, '/admin/alpha')
  assert.equal(adminPages[0].extensionId, 'frontend')
  assert.deepEqual(adminSettings[0], { definition: { key: 'alpha_setting' }, priority: 10 })
  assert.deepEqual(adminSettingOperations, [
    ['replace', 'alpha_setting', { key: 'alpha_setting', replaced: true }],
    ['priority', 'alpha_setting', 20],
    ['remove', 'old_setting'],
  ])
  assert.deepEqual(adminPermissions[0], { definition: { permission: 'alpha.use' }, type: 'moderate', priority: 30 })
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
  assert.equal(extenders.Search, SearchExtender)
  assert.equal(extenders.ThemeMode, ThemeModeExtender)
  assert.equal(extenders.Admin, AdminExtender)
  assert.equal(new Model(UserModel) instanceof ModelExtender, true)
  assert.equal(new Search().gambit('users', query => query) instanceof SearchExtender, true)
  assert.equal(new ThemeMode().add('dark', 'Dark') instanceof ThemeModeExtender, true)
  assert.equal(new Admin().page({ path: '/admin/demo' }) instanceof AdminExtender, true)
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
    components: {
      RouteDemoView: async () => ({ default: 'RouteDemoView' }),
    },
  })

  assert.deepEqual(registered, ['route-demo'])
  assert.equal(routes.length, 1)
  assert.equal(routes[0].meta.extensionId, 'route-demo')
  assert.equal(routes[0].meta.moduleId, 'route-demo')
})

test('registerExtensionForumRoutes removes declared forum routes', () => {
  const removed = []
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
  })

  assert.deepEqual(registered, ['route-demo'])
  assert.deepEqual(removed, ['route-demo'])
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
