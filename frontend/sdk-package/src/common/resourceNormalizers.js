const NORMALIZERS = Object.create(null)

export class ResourceNormalizerExtender {
  constructor() {
    this.items = []
  }

  add(type, normalizer) {
    const normalizedType = normalizeResourceType(type)
    if (normalizedType && typeof normalizer === 'function') {
      this.items.push({ type: normalizedType, normalizer })
    }
    return this
  }

  extend(app, extension = {}) {
    const extensionId = String(
      extension.name
        || extension.id
        || app?.extension?.id
        || app?.application?.extension?.id
        || ''
    ).trim()
    for (const item of this.items) {
      registerResourceNormalizer(item.type, item.normalizer, { extensionId })
    }
  }
}

export function registerResourceNormalizer(type, normalizer, { extensionId = '' } = {}) {
  const normalizedType = normalizeResourceType(type)
  if (!normalizedType || typeof normalizer !== 'function') {
    return null
  }

  const normalizedExtensionId = String(extensionId || '').trim()
  NORMALIZERS[normalizedType] ||= []
  const exists = NORMALIZERS[normalizedType].some(item => {
    return item.normalizer === normalizer && item.extensionId === normalizedExtensionId
  })
  if (!exists) {
    NORMALIZERS[normalizedType].push({
      extensionId: normalizedExtensionId,
      normalizer,
    })
  }
  return normalizer
}

export function resetResourceNormalizers(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  if (!normalizedExtensionId) {
    for (const key of Object.keys(NORMALIZERS)) {
      delete NORMALIZERS[key]
    }
    return
  }
  for (const [type, items] of Object.entries(NORMALIZERS)) {
    NORMALIZERS[type] = items.filter(item => item.extensionId !== normalizedExtensionId)
    if (!NORMALIZERS[type].length) {
      delete NORMALIZERS[type]
    }
  }
}

export function hasResourceNormalizers(type) {
  const normalizedType = normalizeResourceType(type)
  return Array.isArray(NORMALIZERS[normalizedType]) && NORMALIZERS[normalizedType].length > 0
}

export function normalizeResourceItem(type, item) {
  const normalizers = NORMALIZERS[normalizeResourceType(type)] || []
  return normalizers.reduce((currentItem, entry) => {
    return entry.normalizer(currentItem)
  }, { ...(item || {}) })
}

export function getResourceNormalizers(type = '') {
  const normalizedType = normalizeResourceType(type)
  if (normalizedType) {
    return (NORMALIZERS[normalizedType] || []).map(item => item.normalizer)
  }
  return Object.fromEntries(
    Object.entries(NORMALIZERS).map(([key, items]) => [
      key,
      items.map(item => item.normalizer),
    ])
  )
}

export function normalizeResourceType(type) {
  return String(type || '').trim().toLowerCase()
}
