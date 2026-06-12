import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
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
