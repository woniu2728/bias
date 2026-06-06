import test from 'node:test'
import assert from 'node:assert/strict'
import { createTagsResourceState } from './useTagsResourceState.js'

function createResourceStore() {
  const records = new Map()

  return {
    list(type, ids) {
      return ids.map(id => records.get(`${type}:${id}`)).filter(Boolean)
    },
    upsertMany(type, items) {
      return items.map(item => {
        const normalized = {
          children: [],
          ...item,
        }
        records.set(`${type}:${normalized.id}`, normalized)
        return normalized
      })
    },
  }
}

test('tags resource state maps response into resource-backed tags and cloud tags', () => {
  const state = createTagsResourceState({
    resourceStore: createResourceStore(),
  })

  state.applyTagsResponse([
    { id: 1, name: '公告', children: [], last_posted_discussion: { id: 7 } },
    { id: 2, name: '帮助', children: [], last_posted_discussion: { id: 9 } },
  ])

  assert.deepEqual(state.tagIds.value, [1, 2])
  assert.equal(state.tags.value.length, 2)
  assert.deepEqual(state.cloudTags.value.map(tag => tag.id), [1, 2])
  assert.deepEqual(state.trackedDiscussionIds.value, [7, 9])
})

test('tags resource state can reset tag ids', () => {
  const state = createTagsResourceState({
    resourceStore: createResourceStore(),
  })

  state.applyTagsResponse([{ id: 1, name: '公告', children: [] }])
  state.resetTags()

  assert.deepEqual(state.tagIds.value, [])
  assert.deepEqual(state.tags.value, [])
})
