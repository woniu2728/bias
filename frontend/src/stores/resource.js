import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  normalizeDiscussion,
  normalizePost,
  normalizeTag,
  normalizeUser,
  unwrapList,
} from '@/utils/forum'

const NORMALIZERS = {
  users: normalizeUser,
  user: normalizeUser,
  discussions: normalizeDiscussion,
  discussion: normalizeDiscussion,
  posts: normalizePost,
  post: normalizePost,
  tags: normalizeTag,
  tag: normalizeTag,
  notifications: normalizeNotification,
  notification: normalizeNotification,
}

function normalizeNotification(notification = {}) {
  return {
    ...notification,
    is_read: Boolean(notification.is_read),
    from_user: notification.from_user ? normalizeUser(notification.from_user) : null,
  }
}

function normalizeResourceType(type) {
  return String(type || '').trim().toLowerCase()
}

function normalizeItem(type, item) {
  const normalizer = NORMALIZERS[normalizeResourceType(type)]
  return typeof normalizer === 'function' ? normalizer(item) : { ...(item || {}) }
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
    const normalizedItem = normalizeItem(normalizedType, item)
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

  function mergePayload(payload = {}, explicitType = '') {
    const items = []

    if (explicitType) {
      items.push(...upsertMany(explicitType, unwrapList(payload)))
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
    upsert,
    upsertMany,
    remove,
    mergePayload,
  }
})
