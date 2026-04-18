import twemoji from '@twemoji/api'

const htmlCache = new Map()
const textCache = new Map()

function buildTwemojiOptions() {
  return {
    attributes: () => ({
      loading: 'lazy',
      decoding: 'async',
      draggable: 'false'
    })
  }
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
  if (!source || typeof document === 'undefined') {
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
  if (!source || typeof document === 'undefined') {
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
