import { unwrapList } from '@bias/core'

export function normalizeUser(user = {}) {
  return {
    ...user,
    display_name: user.display_name || user.username || '',
    avatar_url: user.avatar_url || '',
    preferences: user.preferences || null,
    groups: unwrapList(user.groups),
  }
}

export function buildUserPath(userOrId) {
  const id = typeof userOrId === 'object' ? userOrId?.id : userOrId
  return `/u/${id}`
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
