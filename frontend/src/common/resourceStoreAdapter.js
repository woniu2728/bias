export function createResourceStoreAdapter({
  resourceStore = null,
  request = null,
  apiBasePath = '',
  search = null,
} = {}) {
  const store = resourceStore || createMemoryResourceStore()
  const models = Object.create(null)
  const records = Object.create(null)

  return {
    resourceStore: store,
    request,
    apiBasePath,
    search,
    models,
    data: records,
    add(type, model) {
      const normalizedType = normalizeType(type)
      if (!normalizedType || typeof model !== 'function') return this
      if (models[normalizedType] && models[normalizedType] !== model) {
        throw new Error(`The model type "${normalizedType}" has already been registered`)
      }
      models[normalizedType] = model
      return this
    },
    createRecord(type, data = {}) {
      const normalizedType = normalizeType(type)
      const ModelClass = models[normalizedType]
      if (!ModelClass) return null
      const record = new ModelClass({
        ...data,
        type: data.type || normalizedType,
      }, this)
      record.exists = Boolean(record.id?.() || record.data?.id)
      return record
    },
    pushPayload(payload = {}, explicitType = '') {
      if (isJsonApiPayload(payload)) {
        return attachPayload(pushJsonApiPayload(this, payload), payload)
      }
      if (explicitType && models[normalizeType(explicitType)]) {
        const items = Array.isArray(payload) ? payload : resolvePlainPayloadItems(payload, explicitType)
        return attachPayload(items.map(item => this.pushObject(item, explicitType)).filter(Boolean), payload)
      }
      const merged = typeof store.mergePayload === 'function'
        ? store.mergePayload(payload, explicitType)
        : []
      return attachPayload(merged, payload)
    },
    pushObject(resource = {}, explicitType = '') {
      const type = explicitType || resource?.type || ''
      if (!type) return null
      if (models[normalizeType(type)]) {
        return pushResourceModel(this, resource, type)
      }
      const item = normalizeResourceObject(resource)
      return typeof store.upsert === 'function' ? store.upsert(type, item) : null
    },
    getById(type, id) {
      const record = records[normalizeType(type)]?.[String(id)]
      if (record) return record
      return typeof store.get === 'function' ? store.get(type, id) : null
    },
    all(type) {
      const normalizedType = normalizeType(type)
      if (records[normalizedType]) return Object.values(records[normalizedType])
      const bucket = store.buckets?.value?.[normalizeType(type)] || store.buckets?.[normalizeType(type)] || {}
      return Object.values(bucket)
    },
    getBy(type, key, value) {
      return this.all(type).find(model => {
        const candidate = typeof model?.[key] === 'function' ? model[key]() : model?.[key]
        return candidate === value
      })
    },
    remove(modelOrType, id = null) {
      const type = typeof modelOrType === 'string'
        ? modelOrType
        : (typeof modelOrType?.type === 'function' ? modelOrType.type() : modelOrType?.type)
      const entityId = id ?? (typeof modelOrType?.id === 'function' ? modelOrType.id() : modelOrType?.id)
      delete records[normalizeType(type)]?.[String(entityId)]
      if (typeof store.remove === 'function') {
        store.remove(type, entityId)
      }
    },
    async find(type, idOrParams = undefined, params = {}, options = {}) {
      if (typeof request !== 'function') {
        throw new Error('Resource store request service is not configured')
      }
      const { url, query } = buildFindRequest(type, idOrParams, params)
      if (query?.filter?.q && typeof this.search?.gambits?.apply === 'function') {
        query.filter = this.search.gambits.apply(type, query.filter)
      }
      const payload = await request({
        method: 'GET',
        url: `${apiBasePath}${url}`,
        params: query,
        ...options,
      })
      return this.pushPayload(payload, type)
    },
    mergePayload(payload = {}, explicitType = '') {
      return this.pushPayload(payload, explicitType)
    },
  }
}

function pushJsonApiPayload(adapter, payload) {
  if (Array.isArray(payload.included)) {
    for (const resource of payload.included) {
      adapter.pushObject(resource)
    }
  }
  const data = payload.data
  if (Array.isArray(data)) {
    return data.map(resource => adapter.pushObject(resource)).filter(Boolean)
  }
  return adapter.pushObject(data)
}

function pushResourceModel(adapter, resource = {}, explicitType = '') {
  const type = normalizeType(explicitType || resource?.type || '')
  if (!type) return null
  const id = resource?.id === undefined || resource?.id === null ? '' : String(resource.id)
  if (typeof adapter.resourceStore?.upsert === 'function') {
    adapter.resourceStore.upsert(type, normalizeResourceObject({
      ...resource,
      type,
    }))
  }
  if (!id) return adapter.createRecord(type, resource)
  recordsForType(adapter.data, type)[id] ||= adapter.createRecord(type, resource)
  recordsForType(adapter.data, type)[id].pushData(resource)
  recordsForType(adapter.data, type)[id].exists = true
  return recordsForType(adapter.data, type)[id]
}

function normalizeResourceObject(resource = {}) {
  if (!resource || typeof resource !== 'object') return {}
  if (!('attributes' in resource) && !('relationships' in resource)) {
    return { ...resource }
  }
  return {
    id: resource.id,
    type: resource.type,
    ...(resource.attributes || {}),
    relationships: resource.relationships || {},
    links: resource.links || {},
    meta: resource.meta || {},
  }
}

function isJsonApiPayload(payload) {
  if (!payload || typeof payload !== 'object' || !('data' in payload)) return false
  const data = payload.data
  if (Array.isArray(data)) {
    return data.every(item => item && typeof item === 'object' && item.type)
  }
  return data && typeof data === 'object' && Boolean(data.type)
}

function buildFindRequest(type, idOrParams, params = {}) {
  let url = `/${String(type || '').trim().replace(/^\/+|\/+$/g, '')}`
  let query = params || {}
  if (Array.isArray(idOrParams)) {
    query = { ...query, filter: { ...(query.filter || {}), id: idOrParams.join(',') } }
  } else if (idOrParams && typeof idOrParams === 'object') {
    query = idOrParams
  } else if (idOrParams !== undefined && idOrParams !== null && idOrParams !== '') {
    url += `/${encodeURIComponent(String(idOrParams))}`
  }
  return { url, query }
}

function attachPayload(result, payload) {
  if (result && typeof result === 'object') {
    Object.defineProperty(result, 'payload', {
      value: payload,
      configurable: true,
      enumerable: false,
      writable: true,
    })
  }
  return result
}

function normalizeType(type) {
  return String(type || '').trim().toLowerCase()
}

function recordsForType(records, type) {
  records[type] ||= {}
  return records[type]
}

function resolvePlainPayloadItems(payload = {}, explicitType = '') {
  if (Array.isArray(payload)) return payload
  if (payload && typeof payload === 'object') {
    const normalizedType = normalizeType(explicitType)
    const collection = payload[normalizedType]
      || payload[`${normalizedType}s`]
      || payload.data
    if (Array.isArray(collection)) return collection
    if (collection && typeof collection === 'object') return [collection]
  }
  return [payload]
}

function createMemoryResourceStore() {
  const buckets = {}
  return {
    buckets,
    upsert(type, item) {
      const normalizedType = normalizeType(type)
      if (!normalizedType || item?.id === undefined || item?.id === null) return item
      buckets[normalizedType] ||= {}
      const id = String(item.id)
      buckets[normalizedType][id] = {
        ...(buckets[normalizedType][id] || {}),
        ...item,
        id,
      }
      return buckets[normalizedType][id]
    },
    get(type, id) {
      return buckets[normalizeType(type)]?.[String(id)] || null
    },
    remove(type, id) {
      delete buckets[normalizeType(type)]?.[String(id)]
    },
    mergePayload(payload = {}, explicitType = '') {
      const items = []
      const type = normalizeType(explicitType)
      if (type) {
        for (const item of Array.isArray(payload) ? payload : [payload]) {
          items.push(this.upsert(type, item))
        }
      }
      return items.filter(Boolean)
    },
  }
}
