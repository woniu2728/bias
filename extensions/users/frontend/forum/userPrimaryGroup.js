export function getUserPrimaryGroup(user = {}) {
  return user?.primary_group || null
}

export function getUserPrimaryGroupIcon(user = {}) {
  return getUserPrimaryGroup(user)?.icon || ''
}

export function getUserPrimaryGroupColor(user = {}, fallback = '') {
  return getUserPrimaryGroup(user)?.color || fallback
}

export function getUserPrimaryGroupLabel(user = {}) {
  return getUserPrimaryGroup(user)?.name || ''
}
