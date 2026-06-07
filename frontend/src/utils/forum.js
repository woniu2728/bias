import { renderTwemojiHtml } from './twemoji.js'
import {
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  resolveDiscussionListActiveFilterCode,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from './discussionList.js'
import { unwrapList } from './forumData.js'

export function normalizeUser(user = {}) {
  return {
    ...user,
    display_name: user.display_name || user.username || '',
    avatar_url: user.avatar_url || '',
    preferences: user.preferences || null,
    groups: unwrapList(user.groups),
  }
}

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

export function normalizePost(post = {}) {
  return {
    ...post,
    content_html: renderTwemojiHtml(post.content_html || ''),
    user: post.user ? normalizeUser(post.user) : null,
    discussion: post.discussion || (post.discussion_id ? {
      id: post.discussion_id,
      title: post.discussion_title || '讨论'
    } : null)
  }
}

export {
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  resolveDiscussionListActiveFilterCode,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
  unwrapList,
}

export function getUserDisplayName(user = {}) {
  return user?.display_name || user?.username || '已删除用户'
}

export function getUserInitial(user = {}) {
  const source = getUserDisplayName(user).trim()
  return source ? source.charAt(0).toUpperCase() : '?'
}

export function getUserAvatarColor(user = {}) {
  if (user?.color) return user.color

  const colors = ['#4d698e', '#e67e22', '#3498db', '#27ae60', '#c0392b', '#8e44ad']
  const identifier = Number(user?.id || 0)
  return colors[identifier % colors.length]
}

export function buildDiscussionPath(discussionOrId) {
  const id = typeof discussionOrId === 'object' ? discussionOrId?.id : discussionOrId
  return `/d/${id}`
}

export function buildUserPath(userOrId) {
  const id = typeof userOrId === 'object' ? userOrId?.id : userOrId
  return `/u/${id}`
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
