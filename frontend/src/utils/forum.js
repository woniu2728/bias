export function unwrapList(payload) {
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload)) return payload
  return []
}

export function normalizeTag(tag = {}) {
  return {
    ...tag,
    color: tag.color || '#6c7a89',
    children: unwrapList(tag.children).map(normalizeTag),
    last_posted_discussion: tag.last_posted_discussion || null
  }
}

export function normalizeDiscussion(discussion = {}) {
  const unreadCount = Number(discussion.unread_count || 0)
  return {
    ...discussion,
    is_sticky: Boolean(discussion.is_sticky ?? discussion.is_pinned),
    is_subscribed: Boolean(discussion.is_subscribed),
    is_unread: Boolean(discussion.is_unread || unreadCount > 0),
    unread_count: unreadCount,
    last_read_post_number: Number(discussion.last_read_post_number || 0),
    tags: unwrapList(discussion.tags).map(normalizeTag)
  }
}

export function normalizePost(post = {}) {
  return {
    ...post,
    like_count: post.like_count ?? post.likes_count ?? 0,
    discussion: post.discussion || (post.discussion_id ? {
      id: post.discussion_id,
      title: post.discussion_title || '讨论'
    } : null)
  }
}

export function flattenTags(tags) {
  return unwrapList(tags).flatMap(tag => {
    const normalized = normalizeTag(tag)
    return [normalized, ...flattenTags(normalized.children)]
  })
}

export function buildDiscussionPath(discussionOrId) {
  const id = typeof discussionOrId === 'object' ? discussionOrId?.id : discussionOrId
  return `/d/${id}`
}

export function buildUserPath(userOrId) {
  const id = typeof userOrId === 'object' ? userOrId?.id : userOrId
  return `/u/${id}`
}

export function buildTagPath(tagOrSlug) {
  const slug = typeof tagOrSlug === 'object' ? tagOrSlug?.slug : tagOrSlug
  return `/t/${slug}`
}

export function formatRelativeTime(dateString) {
  if (!dateString) return '暂无'

  const date = new Date(dateString)
  const diff = Date.now() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 30) return `${days}天前`

  return date.toLocaleDateString('zh-CN')
}

export function formatMonth(dateString) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long'
  })
}
