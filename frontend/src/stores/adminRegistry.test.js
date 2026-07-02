import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import api from '../api/index.js'
import { getAdminNavSections } from '../admin/navigation.js'
import { registerAdminRoute } from '../admin/registry/routes.js'
import { useAdminRegistryStore } from './adminRegistry.js'

test('admin registry derives disabled extension module state from runtime extensions', () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()

  store.applyExtensions([
    {
      id: 'discussions',
      enabled: false,
      module_ids: ['discussions'],
    },
    {
      id: 'posts',
      enabled: false,
      module_ids: ['posts'],
    },
  ])

  assert.equal(store.isModuleEnabled('core'), true)
  assert.equal(store.isModuleEnabled('discussions'), false)
  assert.equal(store.isModuleEnabled('posts'), false)
})

test('admin registry keeps a module enabled when another provider is still enabled', () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()

  store.applyExtensions([
    {
      id: 'alpha',
      enabled: false,
      module_ids: ['shared'],
    },
    {
      id: 'beta',
      enabled: true,
      module_ids: ['shared'],
    },
  ])

  assert.equal(store.isModuleEnabled('shared'), true)
})

test('admin registry waits for an in-flight extension fetch', async () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()
  const originalGet = api.get
  let resolveRequest
  let requestCount = 0

  api.get = async (url) => {
    requestCount += 1
    assert.equal(url, '/admin/extensions')
    return new Promise(resolve => {
      resolveRequest = () => resolve({
        extensions: [{
          id: 'likes',
          name: 'Likes',
          enabled: true,
          module_ids: ['likes'],
        }],
        runtime: { version: 'test' },
      })
    })
  }

  try {
    const firstFetch = store.fetchExtensions()
    const secondFetch = store.fetchExtensions()

    assert.equal(store.loading, true)
    assert.equal(requestCount, 1)
    assert.deepEqual(store.extensions, [])

    resolveRequest()
    await secondFetch
    await firstFetch

    assert.equal(store.loading, false)
    assert.equal(store.loaded, true)
    assert.equal(requestCount, 1)
    assert.deepEqual(store.extensions.map(extension => extension.id), ['likes'])
  } finally {
    api.get = originalGet
  }
})

test('admin navigation hides extension details when a first-class admin page exists', () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()

  store.applyExtensions([
    {
      id: 'users',
      name: 'Users',
      installed: true,
      enabled: true,
      product_visible: true,
      module_ids: ['users'],
    },
    {
      id: 'likes',
      name: 'Likes',
      installed: true,
      enabled: true,
      product_visible: true,
      module_ids: ['likes'],
    },
  ])

  registerAdminRoute({
    path: '/admin/users',
    name: 'admin-users-test-dedup',
    label: '用户管理',
    moduleId: 'users',
    extensionId: 'users',
    navSection: 'core',
    navOrder: 80,
    showInNavigation: true,
  })

  const sections = getAdminNavSections()
  const coreSection = sections.find(section => section.key === 'core')
  const extensionSection = sections.find(section => section.key === 'extensions')

  assert.equal(coreSection.items.some(item => item.path === '/admin/users'), true)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/users'), false)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/likes'), true)
})

test('admin navigation shows installed disabled extensions but hides uninstalled discoveries', () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()

  store.applyExtensions([
    {
      id: 'demo-admin-page',
      name: 'Demo Admin Page',
      installed: false,
      enabled: false,
      product_visible: true,
      module_ids: ['demo-admin-page'],
    },
    {
      id: 'likes',
      name: 'Likes',
      installed: true,
      enabled: false,
      product_visible: true,
      module_ids: ['likes'],
    },
    {
      id: 'fixture-theme',
      name: 'Fixture Theme',
      installed: true,
      enabled: true,
      product_visible: false,
      module_ids: ['fixture-theme'],
    },
  ])

  const sections = getAdminNavSections()
  const extensionSection = sections.find(section => section.key === 'extensions')

  assert.equal(Boolean(extensionSection), true)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/demo-admin-page'), false)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/likes'), true)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/fixture-theme'), false)
})
