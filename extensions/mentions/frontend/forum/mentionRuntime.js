export function detectMentionQuery(content, cursorPosition) {
  const safeContent = String(content || '')
  const safeCursor = Math.max(0, Math.min(cursorPosition ?? safeContent.length, safeContent.length))
  const beforeCursor = safeContent.slice(0, safeCursor)
  const match = beforeCursor.match(/(^|[\s(])@([A-Za-z0-9_.-]{0,30})$/)
  if (!match) return null

  const query = match[2] || ''
  const start = safeCursor - query.length - 1
  return {
    query,
    start,
    end: safeCursor,
  }
}

export function buildMentionReplacement(username) {
  return `@${String(username || '').trim()} `
}

export function buildMentionTrigger(content, start) {
  const before = String(content || '').slice(0, start ?? 0)
  const needsPrefix = before && !/\s$/.test(before)
  return `${needsPrefix ? ' ' : ''}@`
}
