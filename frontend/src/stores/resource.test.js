import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { registerResourceNormalizer, useResourceStore } from './resource.js'

function uniqueType(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

test('resource store applies registered normalizers as a chain', () => {
  setActivePinia(createPinia())
  const type = uniqueType('chain-resource')

  registerResourceNormalizer(type, item => ({
    ...item,
    first: true,
  }))
  registerResourceNormalizer(type, item => ({
    ...item,
    second: item.first ? 'after-first' : 'missing-first',
  }))

  const store = useResourceStore()
  const result = store.upsert(type, { id: 1, name: 'alpha' })

  assert.deepEqual(result, {
    id: 1,
    name: 'alpha',
    first: true,
    second: 'after-first',
  })
})
