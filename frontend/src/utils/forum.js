import { unwrapList } from './forumData.js'
import {
  formatMonth,
  formatRelativeTime,
} from '../common/formatting.js'

export { formatMonth, formatRelativeTime, unwrapList }

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
