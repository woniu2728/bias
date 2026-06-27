import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  hasResourceNormalizers,
  normalizeResourceItem,
  normalizeResourceType,
  registerResourceNormalizer,
  resetResourceNormalizers,
} from '../common/resourceNormalizers.js'
import { unwrapList } from '../utils/forumData.js'

export { registerResourceNormalizer, resetResourceNormalizers }

function inferTypeFromCollectionKey(key) {
  const normalized = normalizeResourceType(key)
  if (!normalized) return ''

  if (hasResourceNormalizers(normalized)) return normalized
  if (normalized.endsWith('ies')) {
    const singular = `${normalized.slice(0, -3)}y`
    if (hasResourceNormalizers(singular)) return singular
  }
  if (normalized.endsWith('s')) {
    const singular = normalized.slice(0, -1)
    if (hasResourceNormalizers(singular)) return singular
  }
  return ''
}

function getEntityId(item) {
  const value = item?.id
  return value === null || value === undefined || value === '' ? null : String(value)
}

export const useResourceStore = defineStore('resource', () => {
  const buckets = ref({})

  function ensureBucket(type) {
    const normalizedType = normalizeResourceType(type)
    if (!normalizedType) return {}
    if (!buckets.value[normalizedType]) {
      buckets.value[normalizedType] = {}
    }
    return buckets.value[normalizedType]
  }

  function upsert(type, item) {
    const normalizedType = normalizeResourceType(type)
    const normalizedItem = normalizeResourceItem(normalizedType, item)
    const entityId = getEntityId(normalizedItem)
    if (!normalizedType || entityId === null) {
      return normalizedItem
    }

    const bucket = ensureBucket(normalizedType)
    bucket[entityId] = {
      ...(bucket[entityId] || {}),
      ...normalizedItem,
    }
    return bucket[entityId]
  }

  function upsertMany(type, items = []) {
    return unwrapList(items).map(item => upsert(type, item))
  }

  function get(type, id) {
    const normalizedType = normalizeResourceType(type)
    const entityId = getEntityId({ id })
    if (!normalizedType || entityId === null) return null
    return buckets.value[normalizedType]?.[entityId] || null
  }

  function list(type, ids = []) {
    return ids
      .map(id => get(type, id))
      .filter(Boolean)
  }

  function remove(type, id) {
    const normalizedType = normalizeResourceType(type)
    const entityId = getEntityId({ id })
    if (!normalizedType || entityId === null) return
    if (!buckets.value[normalizedType]) return
    delete buckets.value[normalizedType][entityId]
  }

  function removeMany(type, ids = []) {
    ids.forEach(id => remove(type, id))
  }

  function patch(type, id, updater) {
    const normalizedType = normalizeResourceType(type)
    const entityId = getEntityId({ id })
    if (!normalizedType || entityId === null) return null

    const currentItem = get(normalizedType, entityId) || { id: entityId }
    const nextPatch = typeof updater === 'function'
      ? updater({ ...currentItem })
      : updater

    if (!nextPatch || typeof nextPatch !== 'object') {
      return get(normalizedType, entityId) || null
    }

    return upsert(normalizedType, {
      ...currentItem,
      ...nextPatch,
      id: nextPatch.id ?? currentItem.id ?? entityId,
    })
  }

  function extractResourceItems(payload = {}) {
    if (!payload || typeof payload !== 'object') return []

    const pairs = []
    for (const [key, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        continue
      }

      if (value && typeof value === 'object' && value.id !== undefined) {
        pairs.push([key, value])
      }
    }

    return pairs
  }

  function extractCollectionItems(payload = {}) {
    if (!payload || typeof payload !== 'object') return []

    const pairs = []
    for (const [key, value] of Object.entries(payload)) {
      const inferredType = inferTypeFromCollectionKey(key)
      if (!inferredType || !Array.isArray(value)) continue
      pairs.push([inferredType, value])
    }
    return pairs
  }

  function mergePayload(payload = {}, explicitType = '') {
    const items = []

    if (explicitType) {
      items.push(...upsertMany(explicitType, unwrapList(payload)))
    }

    for (const [resourceType, resourceItems] of extractCollectionItems(payload)) {
      items.push(...upsertMany(resourceType, resourceItems))
    }

    for (const [resourceType, resourceItem] of extractResourceItems(payload)) {
      items.push(upsert(resourceType, resourceItem))
    }

    return items
  }

  const stats = computed(() => {
    return Object.fromEntries(
      Object.entries(buckets.value).map(([type, bucket]) => [type, Object.keys(bucket || {}).length])
    )
  })

  return {
    buckets,
    stats,
    get,
    list,
    patch,
    upsert,
    upsertMany,
    remove,
    removeMany,
    mergePayload,
  }
})
