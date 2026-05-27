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

export function validateForumExtensionModule(module, extensionId = '') {
  if (!module || typeof module.bootForumExtension !== 'function') {
    const suffix = extensionId ? ` (${extensionId})` : ''
    throw new Error(`扩展前台入口缺少 bootForumExtension 导出${suffix}`)
  }
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

    const module = await loadExtensionForumEntryModule(entryPath, { importers })
    validateForumExtensionModule(module, extensionId)
    await module.bootForumExtension({
      forumStore,
      extension,
      loadedExtensionIds: loadedIds,
    })
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
