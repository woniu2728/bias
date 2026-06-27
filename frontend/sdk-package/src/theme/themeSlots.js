const themeSlots = new Map()

export function registerThemeSlot(name, component, options = {}) {
  const key = String(name || '').trim()
  if (!key || !component) return null
  const record = {
    name: key,
    component,
    order: Number.isFinite(Number(options.order)) ? Number(options.order) : 100,
    extensionId: String(options.extensionId || '').trim(),
    meta: { ...(options.meta || {}) },
  }
  const items = themeSlots.get(key) || []
  const nextItems = [
    ...items.filter(item => item.extensionId !== record.extensionId || item.component !== record.component),
    record,
  ].sort((a, b) => a.order - b.order)
  themeSlots.set(key, nextItems)
  return record
}

export function getThemeSlot(name) {
  const key = String(name || '').trim()
  return key ? [...(themeSlots.get(key) || [])] : []
}

export function getThemeSlots() {
  return Object.fromEntries([...themeSlots.entries()].map(([key, value]) => [key, [...value]]))
}

export function clearThemeSlots() {
  themeSlots.clear()
}
