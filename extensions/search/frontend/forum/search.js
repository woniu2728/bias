function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function stripHtml(value) {
  return String(value ?? '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function truncateText(value, maxLength = 120) {
  const text = stripHtml(value)
  if (text.length <= maxLength) return text
  return `${text.slice(0, Math.max(0, maxLength - 1)).trim()}…`
}

export function buildSearchTokens(query) {
  const normalized = String(query ?? '').trim()
  if (!normalized) return []

  return Array.from(
    new Set(
      normalized
        .split(/\s+/)
        .concat(normalized)
        .map(token => token.trim())
        .filter(Boolean)
    )
  ).sort((left, right) => right.length - left.length)
}

export function highlightSearchText(value, query, maxLength = null) {
  const text = typeof maxLength === 'number' ? truncateText(value, maxLength) : stripHtml(value)
  const tokens = buildSearchTokens(query)

  if (!text) return ''
  if (!tokens.length) return escapeHtml(text)

  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi')
  return escapeHtml(text).replace(pattern, '<mark>$1</mark>')
}
