import api from '../api/index.js'

export function normalizeExtensionForumEntry(entry) {
  const value = String(entry || '').trim()
  if (!value) {
    return ''
  }

  const normalized = value.startsWith('extensions/')
    ? `../../../${value}`
    : value

  return normalized.replace(/\\/g, '/')
}

export async function loadExtensionForumEntryModule(entryPath, { importers = {} } = {}) {
  if (!entryPath) {
    return null
  }

  const importer = importers[entryPath]
  if (!importer) {
    throw new Error(`找不到扩展前台入口: ${entryPath}`)
  }

  return importer()
}

export async function loadEnabledForumExtensions({
  forumStore,
  importers = {},
  fetchPayload,
  loadedExtensionIds,
} = {}) {
  const payload = typeof fetchPayload === 'function'
    ? await fetchPayload()
    : await api.get('/forum')

  const extensions = Array.isArray(payload?.enabled_extensions)
    ? payload.enabled_extensions
    : []

  const loadedIds = loadedExtensionIds || new Set()

  for (const extension of extensions) {
    const extensionId = String(extension?.id || '').trim()
    if (!extensionId || loadedIds.has(extensionId)) {
      continue
    }

    const entryPath = normalizeExtensionForumEntry(extension?.frontend_forum_entry)
    if (!entryPath) {
      continue
    }

    await loadExtensionForumEntryModule(entryPath, { importers })
    loadedIds.add(extensionId)
  }

  if (forumStore && typeof forumStore.applyPublicSettings === 'function') {
    forumStore.applyPublicSettings(payload)
  }

  return {
    payload,
    loadedExtensionIds: loadedIds,
  }
}
