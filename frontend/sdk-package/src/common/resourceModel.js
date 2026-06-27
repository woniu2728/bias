export class ResourceModel {
  constructor(data = {}, store = null) {
    this.data = normalizeModelData(data)
    this.store = store
    this.freshness = new Date()
    this.exists = Boolean(this.data.id)
  }

  id() {
    return this.data.id
  }

  type() {
    return this.data.type
  }

  attribute(name) {
    return this.data.attributes?.[name]
  }

  pushData(data = {}) {
    const normalized = normalizeModelData(data)
    if (normalized.id !== undefined) this.data.id = normalized.id
    if (normalized.type) this.data.type = normalized.type
    if (normalized.attributes) {
      this.data.attributes = {
        ...(this.data.attributes || {}),
        ...normalized.attributes,
      }
    }
    if (normalized.relationships) {
      this.data.relationships = {
        ...(this.data.relationships || {}),
        ...normalizeRelationshipMap(normalized.relationships),
      }
    }
    if (normalized.links) {
      this.data.links = {
        ...(this.data.links || {}),
        ...normalized.links,
      }
    }
    if (normalized.meta) {
      this.data.meta = {
        ...(this.data.meta || {}),
        ...normalized.meta,
      }
    }
    this.freshness = new Date()
    return this
  }

  pushAttributes(attributes = {}) {
    return this.pushData({ attributes })
  }

  copyData() {
    return JSON.parse(JSON.stringify(this.data))
  }

  rawRelationship(name) {
    return this.data.relationships?.[name]?.data
  }

  apiEndpoint() {
    const type = this.type()
    const id = this.id()
    return `/${type}${id ? `/${encodeURIComponent(String(id))}` : ''}`
  }

  async save(attributes = {}, options = {}) {
    if (!this.store || typeof this.store.request !== 'function') {
      throw new Error('Resource model store request service is not configured')
    }
    const oldData = this.copyData()
    const data = {
      type: this.type(),
      attributes: { ...(attributes || {}) },
    }
    if (this.id()) data.id = this.id()
    if (data.attributes.relationships && !this.attribute('relationships')) {
      data.relationships = normalizeSaveRelationships(data.attributes.relationships)
      delete data.attributes.relationships
    }
    this.pushData(data)
    try {
      const payload = await this.store.request({
        method: this.exists ? 'PATCH' : 'POST',
        url: this.store.apiBasePath ? `${this.store.apiBasePath}${this.apiEndpoint()}` : this.apiEndpoint(),
        data: {
          data,
          meta: options.meta,
        },
        ...options,
      })
      const saved = this.store.pushPayload(payload, this.type())
      this.exists = true
      return saved
    } catch (error) {
      this.pushData(oldData)
      throw error
    }
  }

  async delete(data = {}, options = {}) {
    if (!this.exists) return
    if (!this.store || typeof this.store.request !== 'function') {
      throw new Error('Resource model store request service is not configured')
    }
    await this.store.request({
      method: 'DELETE',
      url: this.store.apiBasePath ? `${this.store.apiBasePath}${this.apiEndpoint()}` : this.apiEndpoint(),
      data,
      ...options,
    })
    this.exists = false
    this.store.remove(this)
  }

  static attribute(name, transform = null) {
    return function resourceModelAttribute() {
      const value = this.attribute(name)
      return typeof transform === 'function' ? transform(value) : value
    }
  }

  static hasOne(name) {
    return function resourceModelHasOne() {
      const relationship = this.rawRelationship(name)
      if (Array.isArray(relationship)) {
        throw new Error(`Relationship ${name} on model ${this.type()} is plural`)
      }
      if (relationship === null) return null
      if (!relationship) return false
      return this.store?.getById?.(relationship.type, relationship.id)
    }
  }

  static hasMany(name) {
    return function resourceModelHasMany() {
      const relationship = this.rawRelationship(name)
      if (relationship && !Array.isArray(relationship)) {
        throw new Error(`Relationship ${name} on model ${this.type()} is singular`)
      }
      if (!relationship) return false
      return relationship.map(item => this.store?.getById?.(item.type, item.id))
    }
  }

  static transformDate(value) {
    return value == null ? value : new Date(value)
  }

  static getIdentifier(model) {
    if (!model) return null
    if (model instanceof ResourceModel) {
      return model.id() ? { type: model.type(), id: model.id() } : null
    }
    if (model.type && model.id) {
      return { type: model.type, id: String(model.id) }
    }
    return null
  }
}

export class StoreExtender {
  constructor() {
    this.models = {}
  }

  add(type, model) {
    const normalizedType = normalizeType(type)
    if (!normalizedType || typeof model !== 'function') {
      return this
    }
    if (this.models[normalizedType] && this.models[normalizedType] !== model) {
      throw new Error(`The model type "${normalizedType}" has already been registered with this extender`)
    }
    this.models[normalizedType] = model
    return this
  }

  extend(app) {
    const store = app?.store
    if (!store || typeof store.add !== 'function') {
      throw new Error('Application resource store is not configured')
    }
    for (const [type, model] of Object.entries(this.models)) {
      const existing = store.models?.[type]
      if (existing && existing !== model) {
        throw new Error(`The model type "${type}" has already been registered with the class "${existing.name || 'anonymous'}"`)
      }
      store.add(type, model)
    }
  }
}

export class ModelExtender {
  constructor(model) {
    this.model = model
    this.callbacks = []
  }

  attribute(name, transform = null) {
    this.callbacks.push(() => {
      this.model.prototype[name] = ResourceModel.attribute(name, transform)
    })
    return this
  }

  hasOne(name) {
    this.callbacks.push(() => {
      this.model.prototype[name] = ResourceModel.hasOne(name)
    })
    return this
  }

  hasMany(name) {
    this.callbacks.push(() => {
      this.model.prototype[name] = ResourceModel.hasMany(name)
    })
    return this
  }

  extend() {
    for (const callback of this.callbacks) {
      callback()
    }
  }
}

export function normalizeModelData(data = {}) {
  if (!data || typeof data !== 'object') return {}
  const relationships = normalizeRelationshipMap(data.relationships || {})
  if ('attributes' in data || Object.keys(relationships).length) {
    return {
      type: data.type,
      id: data.id !== undefined && data.id !== null ? String(data.id) : data.id,
      attributes: { ...(data.attributes || {}) },
      relationships,
      links: { ...(data.links || {}) },
      meta: { ...(data.meta || {}) },
    }
  }
  const { id, type, links, meta, ...attributes } = data
  return {
    type,
    id: id !== undefined && id !== null ? String(id) : id,
    attributes,
    relationships,
    links: { ...(links || {}) },
    meta: { ...(meta || {}) },
  }
}

function normalizeSaveRelationships(relationships = {}) {
  return Object.fromEntries(
    Object.entries(relationships || {}).map(([name, value]) => [name, {
      data: Array.isArray(value)
        ? value.map(item => ResourceModel.getIdentifier(item)).filter(Boolean)
        : ResourceModel.getIdentifier(value),
    }])
  )
}

function normalizeRelationshipMap(relationships = {}) {
  return Object.fromEntries(
    Object.entries(relationships || {}).map(([name, value]) => {
      if (value && typeof value === 'object' && 'data' in value) {
        return [name, value]
      }
      if (Array.isArray(value)) {
        return [name, { data: value.map(normalizeIdentifier).filter(Boolean) }]
      }
      return [name, { data: normalizeIdentifier(value) }]
    })
  )
}

function normalizeIdentifier(value) {
  if (!value) return value
  const identifier = ResourceModel.getIdentifier(value)
  if (identifier) return identifier
  if (value.type && value.id !== undefined && value.id !== null) {
    return { type: String(value.type), id: String(value.id) }
  }
  return value
}

function normalizeType(type) {
  return String(type || '').trim().toLowerCase()
}
