export function formatDiscussionTypingNotice(usernames = []) {
  const normalized = usernames
    .map(value => String(value || '').trim())
    .filter(Boolean)

  if (!normalized.length) return ''
  if (normalized.length === 1) return `${normalized[0]} 正在输入...`
  if (normalized.length === 2) return `${normalized[0]}、${normalized[1]} 正在输入...`
  return `${normalized[0]} 等 ${normalized.length} 人正在输入...`
}
