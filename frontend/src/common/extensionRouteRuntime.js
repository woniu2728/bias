export function normalizeExtensionFrontendEntry(entry) {
  const value = String(entry || '').trim()
  if (!value) {
    return ''
  }
  return value.startsWith('extensions/')
    ? `../../../${value}`.replace(/\\/g, '/')
    : value.replace(/\\/g, '/')
}

export function withRuntimeApplication(extension, application) {
  if (!extension || typeof extension !== 'object') {
    return extension
  }
  extension.application = application
  return extension
}

export function registerExtensionFrontendOutput(application, extensionId, frontend, output, { baseUrl } = {}) {
  const registry = application?.exportRegistry
  if (!registry || !output || typeof registry.registerViteOutput !== 'function') {
    return []
  }
  return registry.registerViteOutput(extensionId, frontend, output, {
    baseUrl: baseUrl || resolveFrontendAssetsBaseUrl(),
  })
}

export function resolveExtensionRouteComponent(componentKey, extension, {
  frontend,
  components = {},
  importers = {},
  normalizeEntry = normalizeExtensionFrontendEntry,
} = {}) {
  const normalizedComponent = String(componentKey || '').trim().replace(/\\/g, '/')
  if (!normalizedComponent) {
    return null
  }
  if (components?.[normalizedComponent]) {
    return components[normalizedComponent]
  }

  const extensionId = String(extension?.id || extension?.extension_id || '').trim()
  const candidates = resolveExtensionRouteComponentKeys(normalizedComponent, extension, {
    frontend,
    normalizeEntry,
  })
  for (const key of candidates) {
    const importer = importers?.[key]
    if (typeof importer === 'function') {
      return () => importer().then(resolveDefaultComponent)
    }
  }
  if (extensionId && typeof extension?.application?.exportRegistry?.asyncModuleImport === 'function') {
    return () => importRouteComponentFromExportRegistry(extension.application.exportRegistry, candidates).then(resolveDefaultComponent)
  }
  return null
}

export function resolveExtensionRouteComponentKeys(componentKey, extension = {}, {
  frontend,
  normalizeEntry = normalizeExtensionFrontendEntry,
} = {}) {
  const component = String(componentKey || '').trim().replace(/\\/g, '/')
  if (!component) {
    return []
  }
  const normalizedFrontend = String(frontend || '').trim()
  const extensionId = String(extension?.id || extension?.extension_id || '').trim()
  const entryField = normalizedFrontend ? `frontend_${normalizedFrontend}_entry` : ''
  const entry = String(entryField ? extension?.[entryField] || '' : '').trim().replace(/\\/g, '/')
  const entryDir = entry.split('/').slice(0, -1).join('/')
  const canonical = resolveExtensionRouteComponentPath(component, extensionId, normalizedFrontend, entryDir)
  return dedupe([
    extensionId ? `${extensionId}:${component}` : '',
    extensionId && canonical ? `${extensionId}:${canonical}` : '',
    canonical,
    normalizeEntry(canonical),
    component,
  ])
}

export async function importRouteComponentFromExportRegistry(registry, candidates = []) {
  let lastError = null
  for (const candidate of candidates) {
    const path = routeComponentRegistryPath(candidate)
    if (!path) {
      continue
    }
    try {
      return await registry.asyncModuleImport(path)
    } catch (error) {
      lastError = error
    }
  }
  throw lastError || new Error('No route component chunk found')
}

export function resolveDefaultComponent(module) {
  return module?.default || module
}

function resolveExtensionRouteComponentPath(component, extensionId, frontend, entryDir) {
  if (!component) {
    return ''
  }
  if (component.startsWith('extensions/')) {
    return component
  }
  if ((component.startsWith('./') || component.startsWith('../')) && entryDir) {
    return normalizeRouteComponentPath(`${entryDir}/${component}`)
  }
  if (component.startsWith('./') || component.startsWith('../')) {
    return extensionId
      ? normalizeRouteComponentPath(`extensions/${extensionId}/frontend/${frontend}/${component}`)
      : component
  }
  if (component.includes('/')) {
    return extensionId
      ? normalizeRouteComponentPath(`extensions/${extensionId}/${component}`)
      : normalizeRouteComponentPath(component)
  }
  return extensionId
    ? normalizeRouteComponentPath(`extensions/${extensionId}/frontend/${frontend}/${component}`)
    : component
}

function routeComponentRegistryPath(candidate) {
  const normalized = String(candidate || '').trim().replace(/\\/g, '/')
  if (!normalized) {
    return ''
  }
  if (normalized.includes(':')) {
    const [, id] = normalized.split(/:(.*)/s)
    return routeComponentRegistryPath(id)
  }
  if (normalized.startsWith('extensions/') || normalized.includes('/extensions/')) {
    return normalized
  }
  return ''
}

function dedupe(values) {
  const seen = new Set()
  const output = []
  for (const value of values) {
    const normalized = String(value || '').trim().replace(/\\/g, '/')
    if (!normalized || seen.has(normalized)) {
      continue
    }
    seen.add(normalized)
    output.push(normalized)
  }
  return output
}

function normalizeRouteComponentPath(path) {
  const parts = []
  for (const part of String(path || '').replace(/\\/g, '/').split('/')) {
    if (!part || part === '.') {
      continue
    }
    if (part === '..' && parts.length && parts[parts.length - 1] !== '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/')
}

function resolveFrontendAssetsBaseUrl() {
  return globalThis.bias?.frontendAssetsBaseUrl || '/static/frontend'
}
