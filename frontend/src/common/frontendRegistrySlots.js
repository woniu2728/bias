const frontendRegistrySlots = new Map()

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
