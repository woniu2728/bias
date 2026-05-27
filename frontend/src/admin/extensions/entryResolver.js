import { markRaw } from 'vue'


export function normalizeExtensionAdminEntry(entry) {
  const value = String(entry || '').trim()
  if (!value) {
    return ''
  }

  const normalized = value.startsWith('extensions/')
    ? `../../../../${value}`
    : value

  return normalized.replace(/\\/g, '/')
}


export function resolveAdminEntryFactory(module, surface) {
  if (surface === 'detail') {
    return module.resolveDetailPage
  }
  if (surface === 'operations') {
    return module.resolveOperationsPage
  }
  if (surface === 'permissions') {
    return module.resolvePermissionsPage
  }
  return module.resolveSettingsPage
}

export async function resolveFallbackAdminComponent(
  extension,
  surface,
  {
    fallbacks = [],
  } = {},
) {
  for (const resolver of fallbacks) {
    if (typeof resolver !== 'function') {
      continue
    }
    const component = await resolver({ extension, surface })
    if (component) {
      return markRaw(component.default || component)
    }
  }
  return null
}


export async function resolveExtensionAdminComponent(
  extension,
  surface,
  {
    importers = {},
    builtins = {},
    fallbacks = [],
  } = {},
) {
  const entryPath = normalizeExtensionAdminEntry(extension?.frontend_admin_entry)
  if (!entryPath) {
    return resolveFallbackAdminComponent(extension, surface, { fallbacks })
  }

  const module = await loadExtensionAdminEntryModule(entryPath, {
    importers,
    builtins,
  })
  const factory = resolveAdminEntryFactory(module, surface)
  const component = typeof factory === 'function'
    ? await factory({ extension, surface })
    : null

  if (!component) {
    return resolveFallbackAdminComponent(extension, surface, { fallbacks })
  }

  return markRaw(component.default || component)
}


export async function loadExtensionAdminEntryModule(
  entryPath,
  {
    importers = {},
    builtins = {},
  } = {},
) {
  if (!entryPath) {
    return null
  }

  if (entryPath.startsWith('builtin:')) {
    const builtinEntry = builtins[entryPath]
    if (!builtinEntry) {
      throw new Error(`找不到内置扩展后台入口: ${entryPath}`)
    }
    return builtinEntry
  }

  const importer = importers[entryPath]
  if (!importer) {
    throw new Error(`找不到扩展后台入口: ${entryPath}`)
  }

  return importer()
}
