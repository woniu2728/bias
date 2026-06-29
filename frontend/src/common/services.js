const services = Object.create(null)
const serviceOwners = Object.create(null)

export function registerFrontendService(key, service, options = {}) {
  const normalizedKey = normalizeServiceKey(key)
  if (!normalizedKey || service == null) {
    return null
  }
  const extensionId = normalizeServiceKey(options.extensionId || options.extension_id || '')
  services[normalizedKey] = service
  if (extensionId) {
    serviceOwners[normalizedKey] = extensionId
  } else {
    delete serviceOwners[normalizedKey]
  }
  return service
}

export function getFrontendService(key, fallback = null) {
  const normalizedKey = normalizeServiceKey(key)
  if (!normalizedKey) {
    return fallback
  }
  return Object.prototype.hasOwnProperty.call(services, normalizedKey)
    ? services[normalizedKey]
    : fallback
}

export function requireFrontendService(key) {
  const service = getFrontendService(key)
  if (service == null) {
    throw new Error(`Frontend runtime service is not registered: ${key}`)
  }
  return service
}

export function clearFrontendServices() {
  for (const key of Object.keys(services)) {
    delete services[key]
    delete serviceOwners[key]
  }
}

export function clearFrontendServicesForExtension(extensionId = '') {
  const normalizedExtensionId = normalizeServiceKey(extensionId)
  if (!normalizedExtensionId) {
    clearFrontendServices()
    return
  }
  for (const [key, owner] of Object.entries(serviceOwners)) {
    if (owner === normalizedExtensionId) {
      delete services[key]
      delete serviceOwners[key]
    }
  }
}

function normalizeServiceKey(key) {
  return String(key || '').trim()
}
