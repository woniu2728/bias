import { normalizePost } from '@bias/posts'
import { normalizeUser } from '@bias/users'

export function normalizeDiscussion(discussion = {}) {
  const unreadCount = Number(discussion.unread_count || 0)
  return {
    ...discussion,
    is_sticky: Boolean(discussion.is_sticky ?? discussion.is_pinned),
    is_unread: Boolean(discussion.is_unread || unreadCount > 0),
    unread_count: unreadCount,
    last_read_post_number: Number(discussion.last_read_post_number || 0),
    user: discussion.user ? normalizeUser(discussion.user) : null,
    last_post: discussion.last_post ? normalizePost(discussion.last_post) : null,
  }
}

export function buildDiscussionPath(discussionOrId) {
  const id = typeof discussionOrId === 'object' ? discussionOrId?.id : discussionOrId
  return `/d/${id}`
}
