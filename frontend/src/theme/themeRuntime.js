import { normalizeThemeTokens } from './tokens.js'

let activeTheme = normalizeThemeTokens()
const managedLinkIds = new Set()

export function getActiveTheme() {
  return { ...activeTheme }
}

export function applyTheme(theme = {}, { target = document.documentElement } = {}) {
  const nextTheme = normalizeThemeTokens(theme)
  if (!target) {
    activeTheme = nextTheme
    return getActiveTheme()
  }

  if (activeTheme.className && activeTheme.className !== nextTheme.className) {
    target.classList.remove(activeTheme.className)
  }
  target.classList.add(nextTheme.className)
  target.dataset.biasTheme = nextTheme.id
  target.style.colorScheme = nextTheme.colorScheme

  activeTheme = nextTheme
  return getActiveTheme()
}

export async function loadThemeManifest({ api } = {}) {
  if (!api || typeof api.get !== 'function') {
    return getActiveTheme()
  }
  try {
    const response = await api.get('/forum/theme')
    const payload = response?.data || {}
    applyTheme(payload?.theme || payload || {})
    applyThemeHeadTags(payload?.head_tags || payload?.theme?.head_tags || [])
    return getActiveTheme()
  } catch (_error) {
    return applyTheme(activeTheme)
  }
}

export function bootstrapThemeRuntime(options = {}) {
  return loadThemeManifest(options)
}

export function applyThemeHeadTags(headTags = [], { target = document.head } = {}) {
  if (!target) return []
  const nextIds = new Set()
  const applied = []
  for (const tag of Array.isArray(headTags) ? headTags : []) {
    const payload = tag && typeof tag === 'object' ? tag : {}
    const tagName = String(payload.tag || '').trim().toLowerCase()
    const attributes = payload.attributes && typeof payload.attributes === 'object' ? payload.attributes : {}
    if (tagName !== 'link' || String(attributes.rel || '').toLowerCase() !== 'stylesheet') {
      continue
    }
    const href = String(attributes.href || '').trim()
    if (!href) continue
    const id = String(attributes.id || `bias-theme-style-${hashString(href)}`).trim()
    nextIds.add(id)
    let element = target.querySelector(`#${cssEscape(id)}`)
    if (!element) {
      element = document.createElement('link')
      element.id = id
      element.dataset.biasThemeManaged = 'true'
      target.appendChild(element)
    }
    for (const [name, value] of Object.entries(attributes)) {
      if (value === false || value == null) {
        element.removeAttribute(name)
      } else {
        element.setAttribute(name, String(value))
      }
    }
    managedLinkIds.add(id)
    applied.push(element)
  }
  for (const id of [...managedLinkIds]) {
    if (nextIds.has(id)) continue
    const element = target.querySelector(`#${cssEscape(id)}`)
    if (element?.dataset?.biasThemeManaged === 'true') {
      element.remove()
    }
    managedLinkIds.delete(id)
  }
  return applied
}

function hashString(value) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash).toString(36)
}

function cssEscape(value) {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value)
  }
  return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&')
}
