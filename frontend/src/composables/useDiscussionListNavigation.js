import { computed } from 'vue'
import { getForumNavItems } from '@/forum/registry'
import { flattenTags, normalizeTag, unwrapList } from '@/utils/forum'

const DEFAULT_DISCUSSION_FILTERS = [
  { code: 'all', label: '全部讨论', icon: 'far fa-comments' },
  { code: 'following', label: '关注中', icon: 'fas fa-bell', requires_authenticated_user: true },
]
const SIDEBAR_HIDDEN_DISCUSSION_FILTER_CODES = new Set(['my', 'unread'])

export function useDiscussionListNavigation({
  authStore,
  currentTag,
  currentTagSlug,
  filterOptions,
  isFollowingPage,
  listFilter,
  route,
  tags
}) {
  const isTagsPage = computed(() => route.name === 'tags')
  const isAllDiscussionsPage = computed(() => route.name === 'home' && !currentTagSlug.value)
  const isOwnProfilePage = computed(() => {
    if (!authStore.user) return false

    return (
      route.name === 'profile'
      || (route.name === 'user-profile' && String(route.params.id) === String(authStore.user.id))
    )
  })
  const currentTagContextParent = computed(() => findSidebarContextParent(currentTagSlug.value, tags.value))
  const sidebarPrimaryTagItems = computed(() => buildSidebarPrimaryTagItems(tags.value, currentTagContextParent.value))
  const sidebarSecondaryTagItems = computed(() => buildSidebarSecondaryTagItems(tags.value))
  const sidebarFilterItems = computed(() => buildSidebarFilterItems())
  const hasSidebarTagNavigation = computed(() => tags.value.length > 0)
  const showMoreTagsLink = computed(() => sidebarSecondaryTagItems.value.length > 0)
  const startDiscussionButtonStyle = computed(() => getStartDiscussionButtonStyle(currentTag.value))
  const emptyStateText = computed(() => {
    if (isFollowingPage.value) {
      return '你还没有关注任何讨论。'
    }
    if (listFilter.value === 'my') {
      return '你还没有发起任何讨论。'
    }
    if (listFilter.value === 'unread') {
      return '当前没有未读讨论。'
    }
    if (currentTag.value) {
      return '这个标签下还没有讨论。'
    }
    return '暂无讨论。'
  })

  function buildSidebarFilterItems() {
    const navItems = getForumNavItems({
      authStore,
      surface: 'discussion-sidebar',
    })
    const navItemsByCode = new Map(
      navItems.map(item => [
        item.key === 'home' ? 'all' : item.key,
        item,
      ])
    )
    const sourceFilters = Array.isArray(filterOptions?.value) && filterOptions.value.length
      ? filterOptions.value
      : DEFAULT_DISCUSSION_FILTERS
    const fallbackByCode = new Map(DEFAULT_DISCUSSION_FILTERS.map(item => [item.code, item]))

    return sourceFilters
      .filter(item => !SIDEBAR_HIDDEN_DISCUSSION_FILTER_CODES.has(item.code))
      .map(item => {
        const fallback = fallbackByCode.get(item.code) || {}
        const navItem = navItemsByCode.get(item.code) || {}
        return {
          ...fallback,
          ...navItem,
          ...item,
          label: item.label || navItem.label || fallback.label || item.code,
          icon: item.icon || navItem.icon || fallback.icon || 'far fa-comments',
        }
      })
      .filter(item => !(item.requires_authenticated_user && !authStore.user))
      .map(item => ({
        ...item,
        to: item.to || buildDiscussionFilterLocation(item.code),
        active: isDiscussionFilterActive(item.code),
      }))
  }

  function buildDiscussionFilterLocation(filterCode) {
    if (filterCode === 'following') {
      return '/following'
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

  function isDiscussionFilterActive(filterCode) {
    if (currentTagSlug.value || route.name === 'tags') {
      return false
    }

    if (filterCode === 'following') {
      return isFollowingPage.value
    }

    if (route.name !== 'home') {
      return false
    }

    return listFilter.value === filterCode
  }

  function buildSidebarPrimaryTagItems(sourceTags, contextParent) {
    return sortForumSidebarTags(flattenTags(sourceTags)).filter(tag => {
      const position = normalizeTagPosition(tag.position)
      if (position === null) return false
      if (!tag.parent_id) return true
      return Boolean(contextParent && tag.parent_id === contextParent.id)
    })
  }

  function buildSidebarSecondaryTagItems(sourceTags) {
    return sortForumSidebarTags(flattenTags(sourceTags))
      .filter(tag => normalizeTagPosition(tag.position) === null)
      .slice(0, 3)
  }

  function sortForumSidebarTags(sourceTags) {
    const normalizedTags = unwrapList(sourceTags).map(normalizeTag)
    const tagsById = new Map(normalizedTags.map(tag => [tag.id, tag]))

    return normalizedTags.slice().sort((left, right) => {
      const leftPosition = normalizeTagPosition(left.position)
      const rightPosition = normalizeTagPosition(right.position)

      if (leftPosition === null && rightPosition === null) {
        return Number(right.discussion_count || 0) - Number(left.discussion_count || 0)
      }

      if (rightPosition === null) return -1
      if (leftPosition === null) return 1

      const leftParent = left.parent_id ? tagsById.get(left.parent_id) : null
      const rightParent = right.parent_id ? tagsById.get(right.parent_id) : null

      if (leftParent?.id === rightParent?.id) return leftPosition - rightPosition

      if (leftParent && rightParent) {
        return normalizeTagPosition(leftParent.position) - normalizeTagPosition(rightParent.position)
      }

      if (leftParent) {
        return leftParent.id === right.id
          ? 1
          : normalizeTagPosition(leftParent.position) - rightPosition
      }

      if (rightParent) {
        return rightParent.id === left.id
          ? -1
          : leftPosition - normalizeTagPosition(rightParent.position)
      }

      return 0
    })
  }

  function findSidebarContextParent(targetSlug, sourceTags) {
    if (!targetSlug) return null

    for (const tag of unwrapList(sourceTags).map(normalizeTag)) {
      if (tag.slug === targetSlug) return tag

      if (flattenTags(tag.children).some(child => child.slug === targetSlug)) {
        return tag
      }
    }

    return null
  }

  function normalizeTagPosition(position) {
    return position === null || position === undefined ? null : Number(position)
  }

  function getSidebarTagStyle(tag) {
    return {
      '--tag-color': tag.color || '#6c7a89'
    }
  }

  function getStartDiscussionButtonStyle(tag) {
    if (!tag?.color) return {}

    return {
      '--tag-button-bg': tag.color,
      '--tag-button-text': getContrastColor(tag.color)
    }
  }

  function getContrastColor(color) {
    const hex = String(color || '').trim().replace('#', '')
    if (!/^[\da-fA-F]{6}$/.test(hex)) return '#ffffff'

    const red = parseInt(hex.slice(0, 2), 16)
    const green = parseInt(hex.slice(2, 4), 16)
    const blue = parseInt(hex.slice(4, 6), 16)
    const brightness = (red * 299 + green * 587 + blue * 114) / 1000

    return brightness >= 150 ? '#243447' : '#ffffff'
  }

  function findParentTagSlug(targetSlug, sourceTags) {
    const parent = findSidebarContextParent(targetSlug, sourceTags)
    return parent?.slug || null
  }

  function isSidebarTagActive(tag) {
    if (currentTagSlug.value === tag.slug) return true

    const currentTagParentSlug = findParentTagSlug(currentTagSlug.value, tags.value)
    return Boolean(currentTag.value?.parent_id && currentTagParentSlug === tag.slug)
  }

  return {
    emptyStateText,
    getSidebarTagStyle,
    hasSidebarTagNavigation,
    isAllDiscussionsPage,
    isOwnProfilePage,
    isSidebarTagActive,
    isTagsPage,
    sidebarFilterItems,
    showMoreTagsLink,
    sidebarPrimaryTagItems,
    sidebarSecondaryTagItems,
    startDiscussionButtonStyle
  }
}
