import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
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

test('admin navigation hides extension details when a first-class admin page exists', () => {
  setActivePinia(createPinia())
  const store = useAdminRegistryStore()

  store.applyExtensions([
    {
      id: 'users',
      name: 'Users',
      enabled: true,
      module_ids: ['users'],
    },
    {
      id: 'likes',
      name: 'Likes',
      enabled: true,
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
