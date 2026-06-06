export class ExportRegistry {
  constructor() {
    this.modules = new Map()
    this.chunks = new Map()
    this.chunkModules = new Map()
    this.onLoads = new Map()
    this.chunkBaseUrl = ''
  }

  add(namespace, id, module) {
    return this.register(namespace, id, module)
  }

  register(namespace, id, module) {
    const [resolvedNamespace, resolvedId] = normalizeNamespaceId(namespace, id)
    if (!resolvedNamespace || !resolvedId || module == null) {
      return null
    }
    const key = registryKey(resolvedNamespace, resolvedId)
    this.modules.set(key, module)
    this.flushLoadHandlers(resolvedNamespace, resolvedId, module)
    return module
  }

  registerModule(path, module) {
    const [namespace, id] = this.namespaceAndIdFromPath(path)
    return this.register(namespace, id, module)
  }

  registerChunk(namespace, chunkId, modules = {}, options = {}) {
    const normalizedNamespace = normalizePart(namespace)
    const normalizedChunkId = normalizePart(chunkId)
    if (!normalizedNamespace || !normalizedChunkId || !modules || typeof modules !== 'object') {
      return null
    }
    const key = registryKey(normalizedNamespace, normalizedChunkId)
    const descriptor = normalizeChunkDescriptor(normalizedNamespace, normalizedChunkId, modules, options)
    this.chunks.set(key, descriptor)
    for (const [id, module] of Object.entries(descriptor.modules)) {
      this.chunkModules.set(registryKey(normalizedNamespace, id), {
        chunkId: normalizedChunkId,
        moduleId: id,
        loader: typeof module === 'function' ? module : null,
      })
      if (typeof module !== 'function') {
        this.register(normalizedNamespace, id, module)
      }
    }
    return descriptor
  }

  registerViteOutput(namespace, frontend, output = {}, options = {}) {
    const normalizedNamespace = normalizePart(namespace)
    const normalizedFrontend = normalizePart(frontend || 'default') || 'default'
    if (!normalizedNamespace || !output || typeof output !== 'object') {
      return []
    }
    const chunks = Array.isArray(output.chunks) ? output.chunks : []
    const registered = []
    for (const chunk of chunks) {
      const file = normalizePath(chunk?.file)
      const moduleId = normalizePath(chunk?.module_id || chunk?.moduleId || chunk?.key || file)
      if (!file || !moduleId) {
        continue
      }
      const chunkId = normalizePath(chunk?.id || `${normalizedFrontend}/${file}`)
      const loader = () => import(/* @vite-ignore */ this.chunkUrl(normalizedNamespace, chunkId))
      const revision = normalizePart(chunk?.revision || output.revision || options.revision)
      const descriptor = this.registerChunk(
        normalizedNamespace,
        chunkId,
        { [moduleId]: loader },
        { url: resolveAssetUrl(file, options.baseUrl, revision), urlPath: file, revision }
      )
      if (descriptor) {
        registered.push(descriptor)
      }
    }
    return registered
  }

  addChunkModule(chunkId, moduleId, namespace, pathOrLoader = '', loader = null) {
    const normalizedNamespace = normalizePart(namespace)
    const normalizedChunkId = normalizePart(chunkId)
    const normalizedModuleId = normalizePath(moduleId)
    if (!normalizedNamespace || !normalizedChunkId || !normalizedModuleId) {
      return null
    }
    const chunkKey = registryKey(normalizedNamespace, normalizedChunkId)
    const chunk = this.chunks.get(chunkKey) || normalizeChunkDescriptor(normalizedNamespace, normalizedChunkId, {}, {})
    const moduleLoader = typeof pathOrLoader === 'function' ? pathOrLoader : loader
    const urlPath = typeof pathOrLoader === 'string' ? normalizePath(pathOrLoader) : ''
    chunk.modules[normalizedModuleId] = moduleLoader || urlPath || true
    if (urlPath && !chunk.urlPath) {
      chunk.urlPath = urlPath
    }
    this.chunks.set(chunkKey, chunk)
    this.chunkModules.set(registryKey(normalizedNamespace, normalizedModuleId), {
      chunkId: normalizedChunkId,
      moduleId: normalizedModuleId,
      loader: typeof moduleLoader === 'function' ? moduleLoader : null,
    })
    return chunk
  }

  getChunk(namespaceOrChunkId, chunkId = null) {
    const [namespace, id] = chunkId == null
      ? this.resolveChunkKey(namespaceOrChunkId)
      : [normalizePart(namespaceOrChunkId), normalizePart(chunkId)]
    if (!namespace || !id) {
      return null
    }
    return this.chunks.get(registryKey(namespace, id)) || null
  }

  setChunkBaseUrl(baseUrl = '') {
    this.chunkBaseUrl = String(baseUrl || '').trim().replace(/\/+$/g, '')
    return this
  }

  chunkUrl(namespaceOrChunkId, chunkId = null) {
    const chunk = chunkId == null
      ? this.getChunk(namespaceOrChunkId)
      : this.getChunk(namespaceOrChunkId, chunkId)
    if (!chunk) {
      return null
    }
    if (chunk.url) {
      return chunk.url
    }
    if (!this.chunkBaseUrl || !chunk.urlPath) {
      return chunk.urlPath || null
    }
    return `${this.chunkBaseUrl}/${chunk.namespace}/${chunk.urlPath.replace(/^\/+/g, '')}`
  }

  async loadChunk(namespaceOrChunkId, chunkId = null) {
    if (typeof namespaceOrChunkId === 'function') {
      return this.loadExternalChunk(namespaceOrChunkId, chunkId, arguments[2], arguments[3], arguments[4])
    }
    const chunk = chunkId == null
      ? this.getChunk(namespaceOrChunkId)
      : this.getChunk(namespaceOrChunkId, chunkId)
    if (!chunk) {
      return null
    }
    if (typeof chunk.loader === 'function') {
      const loaded = await chunk.loader(chunk)
      this.registerLoadedChunkModules(chunk, loaded)
      return loaded
    }
    return chunk
  }

  async asyncModuleImport(path) {
    const [namespace, id] = this.namespaceAndIdFromPath(path)
    const loaded = this.get(namespace, id)
    if (loaded) {
      return ensureDefaultExport(loaded)
    }
    const moduleRecord = this.chunkModules.get(registryKey(namespace, id))
    if (!moduleRecord) {
      throw new Error(`No chunk found for module ${namespace}:${id}`)
    }
    if (typeof moduleRecord.loader === 'function') {
      const module = await moduleRecord.loader()
      this.register(namespace, id, module)
      return ensureDefaultExport(module)
    }
    const chunk = this.getChunk(namespace, moduleRecord.chunkId)
    const chunkModule = chunk?.modules?.[moduleRecord.moduleId]
    if (typeof chunkModule === 'function') {
      const module = await chunkModule()
      this.register(namespace, id, module)
      return ensureDefaultExport(module)
    }
    const loadedChunk = await this.loadChunk(namespace, moduleRecord.chunkId)
    const module = this.get(namespace, id)
      || loadedChunk?.[moduleRecord.moduleId]
      || loadedChunk?.default?.[moduleRecord.moduleId]
    if (!module) {
      throw new Error(`No module found for ${namespace}:${id}`)
    }
    this.register(namespace, id, module)
    return ensureDefaultExport(module)
  }

  get(namespace, id) {
    const [resolvedNamespace, resolvedId] = normalizeNamespaceId(namespace, id)
    if (!resolvedNamespace || !resolvedId) {
      return null
    }
    return this.modules.get(registryKey(resolvedNamespace, resolvedId)) || null
  }

  getModule(path) {
    const [namespace, id] = this.namespaceAndIdFromPath(path)
    return this.get(namespace, id)
  }

  unregister(namespace, id) {
    const [resolvedNamespace, resolvedId] = normalizeNamespaceId(namespace, id)
    if (!resolvedNamespace || !resolvedId) {
      return false
    }
    const key = registryKey(resolvedNamespace, resolvedId)
    const removed = this.modules.delete(key)
    this.chunkModules.delete(key)
    this.onLoads.delete(key)
    return removed
  }

  unregisterModule(path) {
    const [namespace, id] = this.namespaceAndIdFromPath(path)
    return this.unregister(namespace, id)
  }

  checkModule(namespace, id) {
    return this.get(namespace, id) || false
  }

  onLoad(namespace, id, handler) {
    const [resolvedNamespace, resolvedId] = normalizeNamespaceId(namespace, id)
    if (!resolvedNamespace || !resolvedId || typeof handler !== 'function') {
      return false
    }
    const loaded = this.get(resolvedNamespace, resolvedId)
    if (loaded) {
      handler(loaded)
      return true
    }
    const key = registryKey(resolvedNamespace, resolvedId)
    const handlers = this.onLoads.get(key) || []
    handlers.push(handler)
    this.onLoads.set(key, handlers)
    return true
  }

  onLoadPath(path, handler) {
    const [namespace, id] = this.namespaceAndIdFromPath(path)
    return this.onLoad(namespace, id, handler)
  }

  namespaceAndIdFromPath(path) {
    const normalized = normalizePath(path)
    if (!normalized) {
      return ['', '']
    }
    const parts = normalized.split('/').filter(Boolean)
    if (parts[0] === 'extensions' && parts.length >= 2) {
      return [parts[1], parts.slice(2).join('/') || 'default']
    }
    if (parts[0] === '..') {
      const extensionIndex = parts.indexOf('extensions')
      if (extensionIndex >= 0 && parts[extensionIndex + 1]) {
        return [
          parts[extensionIndex + 1],
          parts.slice(extensionIndex + 2).join('/') || 'default',
        ]
      }
    }
    if (parts.length === 1) {
      return ['app', parts[0]]
    }
    return [parts[0], parts.slice(1).join('/')]
  }

  clear() {
    this.modules.clear()
    this.chunks.clear()
    this.chunkModules.clear()
    this.onLoads.clear()
  }

  clearNamespace(namespace) {
    const normalizedNamespace = normalizePart(namespace)
    if (!normalizedNamespace) {
      return false
    }
    const prefix = `${normalizedNamespace}:`
    clearMapByKeyPrefix(this.modules, prefix)
    clearMapByKeyPrefix(this.chunks, prefix)
    clearMapByKeyPrefix(this.chunkModules, prefix)
    clearMapByKeyPrefix(this.onLoads, prefix)
    return true
  }

  flushLoadHandlers(namespace, id, module) {
    const key = registryKey(namespace, id)
    const handlers = this.onLoads.get(key) || []
    this.onLoads.delete(key)
    for (const handler of handlers) {
      handler(module)
    }
  }

  resolveChunkKey(chunkId) {
    const normalizedChunkId = normalizePart(chunkId)
    if (!normalizedChunkId) {
      return ['', '']
    }
    if (normalizedChunkId.includes(':')) {
      const [namespace, id] = normalizedChunkId.split(':')
      return [normalizePart(namespace), normalizePart(id)]
    }
    for (const key of this.chunks.keys()) {
      const [namespace, id] = key.split(':')
      if (id === normalizedChunkId) {
        return [namespace, id]
      }
    }
    return ['app', normalizedChunkId]
  }

  registerLoadedChunkModules(chunk, loaded) {
    const modules = loaded?.default && typeof loaded.default === 'object'
      ? { ...loaded, ...loaded.default }
      : loaded
    if (!modules || typeof modules !== 'object') {
      return
    }
    for (const [id, module] of Object.entries(modules)) {
      this.register(chunk.namespace, id, module)
    }
  }

  async loadExternalChunk(original, url, done, key, chunkId) {
    const resolvedUrl = this.chunkUrl(chunkId) || url
    return original(resolvedUrl, done, key, chunkId)
  }
}

export function ensureExportRegistry(target = globalThis) {
  if (!target.bias || typeof target.bias !== 'object') {
    target.bias = {}
  }
  if (!(target.bias.reg instanceof ExportRegistry)) {
    target.bias.reg = new ExportRegistry()
  }
  return target.bias.reg
}

function normalizeNamespaceId(namespace, id) {
  if (id === undefined || id === null) {
    const normalizedPath = normalizePath(namespace)
    const parts = normalizedPath.split('/').filter(Boolean)
    if (parts.length <= 1) {
      return ['app', parts[0] || '']
    }
    return [parts[0], parts.slice(1).join('/')]
  }
  return [normalizePart(namespace), normalizePath(id)]
}

function normalizePath(value) {
  return String(value || '').trim().replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

function normalizePart(value) {
  return String(value || '').trim()
}

function registryKey(namespace, id) {
  return `${namespace}:${id}`
}

function clearMapByKeyPrefix(map, prefix) {
  for (const key of [...map.keys()]) {
    if (String(key).startsWith(prefix)) {
      map.delete(key)
    }
  }
}

function resolveAssetUrl(file, baseUrl = '', revision = '') {
  const normalizedFile = normalizePath(file)
  const normalizedBaseUrl = String(baseUrl || '').trim().replace(/\/+$/g, '')
  const normalizedRevision = normalizePart(revision)
  const withRevision = url => normalizedRevision ? appendQuery(url, 'v', normalizedRevision) : url
  if (!normalizedBaseUrl) {
    return withRevision(normalizedFile)
  }
  return withRevision(`${normalizedBaseUrl}/${normalizedFile.replace(/^\/+/g, '')}`)
}

function normalizeChunkDescriptor(namespace, chunkId, modules, options = {}) {
  const descriptor = modules && !Array.isArray(modules) && (
    Object.prototype.hasOwnProperty.call(modules, 'modules')
    || Object.prototype.hasOwnProperty.call(modules, 'loader')
    || Object.prototype.hasOwnProperty.call(modules, 'url')
    || Object.prototype.hasOwnProperty.call(modules, 'urlPath')
  )
    ? modules
    : { modules }
  return {
    namespace,
    chunkId,
    id: chunkId,
    modules: { ...(descriptor.modules || {}) },
    loader: typeof descriptor.loader === 'function' ? descriptor.loader : (typeof options.loader === 'function' ? options.loader : null),
    url: normalizePart(descriptor.url || options.url),
    urlPath: normalizePath(descriptor.urlPath || descriptor.path || options.urlPath || options.path || ''),
    revision: normalizePart(descriptor.revision || options.revision || ''),
  }
}

function appendQuery(url, key, value) {
  const normalizedUrl = String(url || '').trim()
  if (!normalizedUrl || normalizedUrl.includes(`${key}=`)) {
    return normalizedUrl
  }
  return `${normalizedUrl}${normalizedUrl.includes('?') ? '&' : '?'}${encodeURIComponent(key)}=${encodeURIComponent(value)}`
}

function ensureDefaultExport(module) {
  if (module && typeof module === 'object' && !Object.prototype.hasOwnProperty.call(module, 'default')) {
    module.default = module
  }
  return module
}

export default ExportRegistry
