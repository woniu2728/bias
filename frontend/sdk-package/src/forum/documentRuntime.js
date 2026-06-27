const titleDriverRegistry = new Map()
const contentCallbackRegistry = new Map()
const titleDriverScopes = new Map()
const contentCallbackScopes = new Map()
let activeDocumentRuntime = normalizeExtensionDocumentPayload({})

import { getCurrentExtensionId } from '../common/extensionScope.js'

export function registerExtensionTitleDriver(key, driver) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey || typeof driver !== 'function') {
    return false
  }
  titleDriverRegistry.set(normalizedKey, driver)
  recordRegistryScope(titleDriverScopes, normalizedKey)
  return true
}

export function registerExtensionDocumentContent(key, callback) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey || typeof callback !== 'function') {
    return false
  }
  contentCallbackRegistry.set(normalizedKey, callback)
  recordRegistryScope(contentCallbackScopes, normalizedKey)
  return true
}

export function clearExtensionDocumentRuntime() {
  activeDocumentRuntime = normalizeExtensionDocumentPayload({})
  titleDriverRegistry.clear()
  contentCallbackRegistry.clear()
  titleDriverScopes.clear()
  contentCallbackScopes.clear()
}

export function clearExtensionDocumentRuntimeForExtension(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  clearScopedRegistry(titleDriverRegistry, titleDriverScopes, normalizedExtensionId)
  clearScopedRegistry(contentCallbackRegistry, contentCallbackScopes, normalizedExtensionId)
  if (!normalizedExtensionId) {
    activeDocumentRuntime = normalizeExtensionDocumentPayload({})
    return
  }
  activeDocumentRuntime = {
    ...activeDocumentRuntime,
    titleDrivers: activeDocumentRuntime.titleDrivers.filter(item => item.extension_id !== normalizedExtensionId),
    contentCallbacks: activeDocumentRuntime.contentCallbacks.filter(item => item.extension_id !== normalizedExtensionId),
    preloads: activeDocumentRuntime.preloads.filter(item => item?.extension_id !== normalizedExtensionId),
    headTags: activeDocumentRuntime.headTags.filter(item => item?.extension_id !== normalizedExtensionId),
  }
}

export function normalizeExtensionDocumentPayload(payload) {
  const documentPayload = payload?.extension_document || payload || {}
  const preloads = Array.isArray(documentPayload.preloads)
    ? documentPayload.preloads.filter(Boolean)
    : []
  const documentAttributes = documentPayload.document_attributes && typeof documentPayload.document_attributes === 'object'
    ? { ...documentPayload.document_attributes }
    : {}
  const titleDrivers = Array.isArray(documentPayload.title_drivers)
    ? documentPayload.title_drivers.filter((item) => item && item.driver)
    : []
  const contentCallbacks = Array.isArray(documentPayload.content_callbacks)
    ? documentPayload.content_callbacks
      .filter((item) => item && item.callback)
      .map((item) => ({
        ...item,
        priority: Number.parseInt(item.priority || 0, 10) || 0,
      }))
      .sort((a, b) => b.priority - a.priority)
    : []
  const headTags = Array.isArray(documentPayload.head_tags)
    ? documentPayload.head_tags.filter(Boolean)
    : []
  const themeVariables = documentPayload.theme_variables && typeof documentPayload.theme_variables === 'object'
    ? { ...documentPayload.theme_variables }
    : {}

  return {
    preloads,
    documentAttributes,
    themeVariables,
    titleDrivers,
    contentCallbacks,
    headTags,
  }
}

export function applyExtensionDocumentPayload(payload, { documentRef = globalThis.document } = {}) {
  const normalized = normalizeExtensionDocumentPayload(payload)
  activeDocumentRuntime = normalized
  if (!documentRef) {
    return normalized
  }

  applyExtensionPreloads(normalized.preloads, documentRef, 'static')
  applyExtensionDocumentAttributes(normalized.documentAttributes, documentRef)
  applyExtensionThemeVariables(normalized.themeVariables, documentRef)
  applyExtensionHeadTags(normalized.headTags, documentRef, 'static')
  return normalized
}

export function resolveExtensionPageMeta(meta = {}, context = {}) {
  const state = {
    meta: { ...(meta || {}) },
    preloads: [],
    documentAttributes: {},
    themeVariables: {},
    headTags: [],
  }

  for (const item of activeDocumentRuntime.contentCallbacks) {
    const callback = resolveRegisteredCallback(contentCallbackRegistry, item.callback)
    if (!callback) {
      continue
    }
    mergeDocumentMutation(state, callback({
      ...context,
      extensionId: item.extension_id,
      meta: state.meta,
    }))
  }

  for (const item of activeDocumentRuntime.titleDrivers) {
    const driver = resolveRegisteredCallback(titleDriverRegistry, item.driver)
    if (!driver) {
      continue
    }
    const result = driver({
      ...context,
      extensionId: item.extension_id,
      meta: state.meta,
    })
    if (typeof result === 'string') {
      state.meta.title = result
    } else {
      mergeDocumentMutation(state, result)
    }
  }

  return state
}

export function applyExtensionDocumentState(state, { documentRef = globalThis.document } = {}) {
  if (!documentRef || !state) {
    return state
  }
  applyExtensionPreloads(state.preloads || [], documentRef, 'dynamic')
  applyExtensionDocumentAttributes(state.documentAttributes || {}, documentRef)
  applyExtensionThemeVariables(state.themeVariables || {}, documentRef, 'dynamic')
  applyExtensionHeadTags(state.headTags || [], documentRef, 'dynamic')
  return state
}

function resolveRegisteredCallback(registry, callback) {
  if (typeof callback === 'function') {
    return callback
  }
  const key = String(callback || '').trim()
  return key ? registry.get(key) : null
}

function mergeDocumentMutation(state, mutation) {
  if (!mutation || typeof mutation !== 'object') {
    return
  }
  if (mutation.meta && typeof mutation.meta === 'object') {
    state.meta = { ...state.meta, ...mutation.meta }
  }
  if (typeof mutation.title === 'string') {
    state.meta.title = mutation.title
  }
  if (Array.isArray(mutation.preloads)) {
    state.preloads.push(...mutation.preloads.filter(Boolean))
  }
  if (mutation.documentAttributes && typeof mutation.documentAttributes === 'object') {
    state.documentAttributes = { ...state.documentAttributes, ...mutation.documentAttributes }
  }
  if (mutation.document_attributes && typeof mutation.document_attributes === 'object') {
    state.documentAttributes = { ...state.documentAttributes, ...mutation.document_attributes }
  }
  if (Array.isArray(mutation.headTags)) {
    state.headTags.push(...mutation.headTags.filter(Boolean))
  }
  if (Array.isArray(mutation.head_tags)) {
    state.headTags.push(...mutation.head_tags.filter(Boolean))
  }
  if (mutation.themeVariables && typeof mutation.themeVariables === 'object') {
    state.themeVariables = { ...(state.themeVariables || {}), ...mutation.themeVariables }
  }
  if (mutation.theme_variables && typeof mutation.theme_variables === 'object') {
    state.themeVariables = { ...(state.themeVariables || {}), ...mutation.theme_variables }
  }
}

function applyExtensionPreloads(preloads, documentRef, scope = 'static') {
  const head = documentRef.head
  if (!head || typeof documentRef.createElement !== 'function') {
    return
  }

  removeExistingExtensionNodes(head, `[data-bias-extension-preload-scope="${scope}"]`)
  for (const preload of preloads) {
    const attributes = normalizePreloadAttributes(preload)
    if (!attributes.href) {
      continue
    }
    const link = documentRef.createElement('link')
    link.setAttribute('rel', attributes.rel || 'preload')
    link.setAttribute('data-bias-extension-preload', 'true')
    link.setAttribute('data-bias-extension-preload-scope', scope)
    for (const [key, value] of Object.entries(attributes)) {
      if (key === 'rel' || value === undefined || value === null || value === false) {
        continue
      }
      link.setAttribute(normalizeAttributeName(key), value === true ? '' : String(value))
    }
    head.appendChild(link)
  }
}

function applyExtensionDocumentAttributes(attributes, documentRef) {
  const target = documentRef.documentElement
  if (!target || typeof target.setAttribute !== 'function') {
    return
  }

  for (const [key, value] of Object.entries(attributes || {})) {
    const name = normalizeAttributeName(key)
    if (!name || value === undefined || value === null || value === false) {
      continue
    }
    if (name === 'class') {
      applyExtensionDocumentClasses(target, value)
      continue
    }
    target.setAttribute(name, value === true ? '' : String(value))
  }
}

function applyExtensionDocumentClasses(target, value) {
  const classes = normalizeClassList(value)
  if (!classes.length) {
    return
  }
  if (target.classList && typeof target.classList.add === 'function') {
    target.classList.add(...classes)
    return
  }
  const current = typeof target.getAttribute === 'function' ? target.getAttribute('class') : ''
  const merged = Array.from(new Set([
    ...String(current || '').split(/\s+/).filter(Boolean),
    ...classes,
  ]))
  target.setAttribute('class', merged.join(' '))
}

function applyExtensionThemeVariables(variables, documentRef, scope = 'static') {
  const entries = Object.entries(variables || {})
    .map(([name, value]) => [normalizeCssVariableName(name), value])
    .filter(([name, value]) => name && value !== undefined && value !== null && value !== false)
  if (!entries.length) {
    return
  }

  const head = documentRef.head
  if (!head || typeof documentRef.createElement !== 'function') {
    return
  }
  removeExistingExtensionNodes(head, `[data-bias-extension-theme-scope="${scope}"]`)
  const style = documentRef.createElement('style')
  style.setAttribute('data-bias-extension-theme', 'true')
  style.setAttribute('data-bias-extension-theme-scope', scope)
  style.textContent = `:root{${entries.map(([name, value]) => `${name}:${String(value)};`).join('')}}`
  head.appendChild(style)
}

function applyExtensionHeadTags(headTags, documentRef, scope = 'static') {
  const head = documentRef.head
  if (!head || typeof documentRef.createElement !== 'function') {
    return
  }
  removeExistingExtensionNodes(head, `[data-bias-extension-head-scope="${scope}"]`)
  for (const definition of headTags || []) {
    const tag = normalizeHeadTag(definition)
    if (!tag.tag) {
      continue
    }
    const element = documentRef.createElement(tag.tag)
    element.setAttribute('data-bias-extension-head', 'true')
    element.setAttribute('data-bias-extension-head-scope', scope)
    for (const [key, value] of Object.entries(tag.attributes)) {
      if (value === undefined || value === null || value === false) {
        continue
      }
      element.setAttribute(normalizeAttributeName(key), value === true ? '' : String(value))
    }
    if (tag.text) {
      element.textContent = String(tag.text)
    }
    head.appendChild(element)
  }
}

function normalizePreloadAttributes(preload) {
  if (typeof preload === 'string') {
    return { href: preload }
  }
  if (!preload || typeof preload !== 'object') {
    return {}
  }
  return { ...preload }
}

function normalizeHeadTag(definition) {
  if (!definition || typeof definition !== 'object') {
    return { tag: '', attributes: {}, text: '' }
  }
  const tag = String(definition.tag || definition.name || '').trim().toLowerCase()
  const attributes = {
    ...(definition.attributes && typeof definition.attributes === 'object' ? definition.attributes : {}),
    ...definition,
  }
  delete attributes.tag
  if (!definition.tag) {
    delete attributes.name
  }
  delete attributes.text
  delete attributes.attributes
  return {
    tag,
    attributes,
    text: definition.text || '',
  }
}

function normalizeAttributeName(name) {
  return String(name || '').trim().replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)
}

function normalizeCssVariableName(name) {
  const normalized = normalizeAttributeName(name)
  if (!normalized) return ''
  return normalized.startsWith('--') ? normalized : `--${normalized}`
}

function normalizeClassList(value) {
  if (typeof value === 'string') {
    return value.split(/\s+/).map((item) => item.trim()).filter(Boolean)
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => normalizeClassList(item))
  }
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .filter(([, enabled]) => Boolean(enabled))
      .map(([name]) => String(name || '').trim())
      .filter(Boolean)
  }
  return []
}

function removeExistingExtensionNodes(parent, selector) {
  if (!parent || typeof parent.querySelectorAll !== 'function') {
    return
  }
  for (const node of parent.querySelectorAll(selector)) {
    node.remove?.()
  }
}

function recordRegistryScope(scopeRegistry, key) {
  const extensionId = String(getCurrentExtensionId() || '').trim()
  if (extensionId) {
    scopeRegistry.set(key, extensionId)
  }
}

function clearScopedRegistry(registry, scopeRegistry, extensionId = '') {
  for (const [key, itemExtensionId] of scopeRegistry.entries()) {
    if (!extensionId || itemExtensionId === extensionId) {
      registry.delete(key)
      scopeRegistry.delete(key)
    }
  }
}
