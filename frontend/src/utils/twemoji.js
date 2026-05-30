import twemoji from '@twemoji/api'

const htmlCache = new Map()
const textCache = new Map()
let twemojiBaseUrlOverride = ''
let twemojiEnabled = false

function buildTwemojiOptions() {
  const options = {
    attributes: () => ({
      loading: 'lazy',
      decoding: 'async',
      draggable: 'false'
    })
  }
  if (twemojiBaseUrlOverride) {
    options.base = twemojiBaseUrlOverride
  }
  return options
}

function parseHtml(html) {
  const documentRef = document.implementation.createHTMLDocument('')
  documentRef.body.innerHTML = html
  return documentRef.body
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function renderTwemojiHtml(html) {
  const source = String(html || '')
  if (!source || typeof document === 'undefined' || !twemojiEnabled) {
    return source
  }

  const cached = htmlCache.get(source)
  if (cached) {
    return cached
  }

  const parsedBody = parseHtml(source)
  const renderedBody = twemoji.parse(parsedBody, buildTwemojiOptions())
  const renderedHtml = renderedBody.innerHTML

  htmlCache.set(source, renderedHtml)
  return renderedHtml
}

export function renderTwemojiText(text) {
  const source = String(text || '')
  if (!source || typeof document === 'undefined' || !twemojiEnabled) {
    return escapeHtml(source)
  }

  const cached = textCache.get(source)
  if (cached) {
    return cached
  }

  const renderedHtml = renderTwemojiHtml(escapeHtml(source))
  textCache.set(source, renderedHtml)
  return renderedHtml
}

export function setTwemojiBaseUrl(url) {
  const normalized = String(url || '').trim()
  if (twemojiBaseUrlOverride === normalized) {
    return
  }
  twemojiBaseUrlOverride = normalized
  htmlCache.clear()
  textCache.clear()
}

export function setTwemojiEnabled(value) {
  const nextValue = Boolean(value)
  if (twemojiEnabled === nextValue) {
    return
  }
  twemojiEnabled = nextValue
  htmlCache.clear()
  textCache.clear()
}
