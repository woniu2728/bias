const frontendRegistrySlots = getSharedFrontendRegistrySlots()

function getSharedFrontendRegistrySlots() {
  const key = '__biasFrontendRegistrySlots'
  const root = globalThis
  if (!root[key] || !(root[key] instanceof Map)) {
    root[key] = new Map()
  }
  return root[key]
}

export function getFrontendRegistrySlot(name) {
  const key = String(name || '').trim()
  if (!key) {
    throw new Error('Frontend registry slot requires a name')
  }
  if (!frontendRegistrySlots.has(key)) {
    frontendRegistrySlots.set(key, [])
  }
  return frontendRegistrySlots.get(key)
}

export function getFrontendRegistrySlots(names = []) {
  return Array.from(names, name => getFrontendRegistrySlot(name))
}
