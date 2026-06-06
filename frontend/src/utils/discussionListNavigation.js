export function buildDiscussionFilterLocation(filterItem) {
  const filterCode = filterItem?.code
  const routePath = String(filterItem?.route_path || '').trim()

  if (routePath && routePath !== '/') {
    return routePath
  }

  if (filterCode === 'all') {
    return '/'
  }

  return {
    path: '/',
    query: {
      filter: filterCode,
    },
  }
}

export function isDiscussionFilterActive({
  contextSubjectKey,
  routeName,
  isFollowingPage,
  listFilter,
  filterCode,
}) {
  if (contextSubjectKey) {
    return false
  }

  if (filterCode === 'following') {
    return Boolean(isFollowingPage)
  }

  if (routeName !== 'home') {
    return false
  }

  return listFilter === filterCode
}

export function getDiscussionListContrastColor(color) {
  const hex = String(color || '').trim().replace('#', '')
  if (!/^[\da-fA-F]{6}$/.test(hex)) return '#ffffff'

  const red = parseInt(hex.slice(0, 2), 16)
  const green = parseInt(hex.slice(2, 4), 16)
  const blue = parseInt(hex.slice(4, 6), 16)
  const brightness = (red * 299 + green * 587 + blue * 114) / 1000

  return brightness >= 150 ? '#243447' : '#ffffff'
}

export function getDiscussionListStartButtonStyle(subject) {
  if (!subject?.color) return {}

  return {
    '--tag-button-bg': subject.color,
    '--tag-button-text': getDiscussionListContrastColor(subject.color),
  }
}
