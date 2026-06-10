export function resolveProfileMetaPayload(user) {
  if (!user) return null

  const displayName = user.display_name || user.username || `用户 ${user.id}`
  const bio = String(user.bio || '').replace(/\s+/g, ' ').trim()

  return {
    title: `${displayName} 的主页`,
    description: bio || `${displayName} 在论坛发布了 ${user.discussion_count || 0} 个讨论和 ${user.comment_count || 0} 条回复。`,
    canonicalUrl: `/u/${user.username || user.id}`,
  }
}
