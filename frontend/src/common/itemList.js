export class ItemList {
  constructor(items = {}) {
    this._items = Object.create(null)
    for (const [key, value] of Object.entries(items || {})) {
      if (value && typeof value === 'object' && 'content' in value) {
        this.add(key, value.content, value.priority)
      }
    }
  }

  isEmpty() {
    return Object.keys(this._items).length === 0
  }

  has(key) {
    return Object.prototype.hasOwnProperty.call(this._items, String(key || ''))
  }

  get(key) {
    return this._items[String(key || '')]?.content
  }

  getPriority(key) {
    return Number(this._items[String(key || '')]?.priority || 0)
  }

  add(key, content, priority = 0) {
    const normalizedKey = String(key || '').trim()
    if (!normalizedKey) {
      return this
    }
    this._items[normalizedKey] = {
      content,
      priority: Number(priority) || 0,
    }
    return this
  }

  setContent(key, content) {
    const normalizedKey = String(key || '').trim()
    if (!this.has(normalizedKey)) {
      throw new Error(`[ItemList] Cannot set content of item. Key \`${normalizedKey}\` is not present.`)
    }
    if (content !== null) {
      this._items[normalizedKey].content = content
    }
    return this
  }

  setPriority(key, priority = 0) {
    const normalizedKey = String(key || '').trim()
    if (!this.has(normalizedKey)) {
      throw new Error(`[ItemList] Cannot set priority of item. Key \`${normalizedKey}\` is not present.`)
    }
    this._items[normalizedKey].priority = Number(priority) || 0
    return this
  }

  remove(key) {
    delete this._items[String(key || '').trim()]
    return this
  }

  merge(otherList) {
    if (!otherList || typeof otherList.toObject !== 'function') {
      return this
    }
    for (const [key, item] of Object.entries(otherList.toObject())) {
      this.add(key, item.content, item.priority)
    }
    return this
  }

  toArray(options = false) {
    const { keepPrimitives, context, resolve } = normalizeToArrayOptions(options)
    return Object.entries(this._items)
      .map(([key, item]) => ({
        key,
        content: normalizeItemContent(item.content, key, { keepPrimitives }),
        priority: Number(item.priority || 0),
      }))
      .sort((left, right) => right.priority - left.priority)
      .map(item => {
        if (typeof resolve === 'function') {
          return resolve(item.content, context, item.key)
        }
        return item.content
      })
      .filter(item => item !== null && item !== undefined)
  }

  toObject() {
    return Object.fromEntries(
      Object.entries(this._items).map(([key, item]) => [
        key,
        {
          content: item.content,
          itemName: key,
          priority: Number(item.priority || 0),
        },
      ])
    )
  }
}

function normalizeItemContent(content, key, { keepPrimitives = true } = {}) {
  if (!keepPrimitives || isObject(content)) {
    return createItemContentProxy(isObject(content) ? content : Object(content), key)
  }
  return content
}

function normalizeToArrayOptions(options) {
  if (typeof options === 'boolean') {
    return {
      keepPrimitives: options,
      context: null,
      resolve: null,
    }
  }
  const value = options && typeof options === 'object' ? options : {}
  return {
    keepPrimitives: Boolean(value.keepPrimitives),
    context: value.context || null,
    resolve: typeof value.resolve === 'function' ? value.resolve : null,
  }
}

function createItemContentProxy(content, key) {
  return new Proxy(content, {
    get(target, property, receiver) {
      if (property === 'itemName') return key
      const value = Reflect.get(target, property, receiver)
      if (typeof value === 'function' && isPrimitiveWrapper(target)) {
        return value.bind(target)
      }
      return value
    },
    set(target, property, value, receiver) {
      if (property === 'itemName') {
        throw new Error('`itemName` property is read-only')
      }
      return Reflect.set(target, property, value, receiver)
    },
  })
}

function isObject(value) {
  return value !== null && typeof value === 'object'
}

function isPrimitiveWrapper(value) {
  return value instanceof String || value instanceof Number || value instanceof Boolean
}

export function itemContentValue(content) {
  if (isPrimitiveWrapper(content)) {
    return content.valueOf()
  }
  return content
}

export default ItemList
