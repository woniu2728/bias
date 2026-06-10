import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { ResourceNormalizerExtender } from '../common/resourceNormalizers.js'
import { registerResourceNormalizer, resetResourceNormalizers, useResourceStore } from './resource.js'

function uniqueType(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

test('resource store applies registered normalizers as a chain', () => {
  setActivePinia(createPinia())
  const type = uniqueType('chain-resource')
  resetResourceNormalizers(type)

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

test('resource normalizer extender scopes duplicate registration by extension', () => {
  setActivePinia(createPinia())
  const type = uniqueType('extender-resource')
  const normalizer = item => ({
    ...item,
    count: Number(item.count || 0) + 1,
  })

  const extender = new ResourceNormalizerExtender().add(type, normalizer)
  extender.extend({}, { name: 'alpha' })
  extender.extend({}, { name: 'alpha' })

  const store = useResourceStore()
  assert.equal(store.upsert(type, { id: 1 }).count, 1)

  resetResourceNormalizers('alpha')
  assert.equal(store.upsert(type, { id: 2 }).count, undefined)
})
