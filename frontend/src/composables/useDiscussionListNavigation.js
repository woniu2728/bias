import { computed } from 'vue'
import { getEmptyState, getForumNavItems, getStateBlock, getUiCopy } from '../forum/frontendRegistry.js'
import { flattenTags, normalizeTag, unwrapList } from '../utils/forumData.js'
import {
  buildDiscussionFilterLocation,
  buildDiscussionListPrimaryTagItems,
  buildDiscussionListSecondaryTagItems,
  findDiscussionListSidebarContextParent,
  getDiscussionListStartButtonStyle,
  isDiscussionFilterActive,
  isDiscussionSidebarTagActive,
} from '../utils/discussionListNavigation.js'

const DEFAULT_DISCUSSION_FILTERS = [
  { code: 'all', icon: 'far fa-comments', sidebar_visible: true, route_path: '/' },
  { code: 'following', icon: 'fas fa-bell', requires_authenticated_user: true, sidebar_visible: true, route_path: '/following' },
]

export function createDiscussionListNavigation({
  authStore,
  currentTag,
  currentTagSlug,
  filterOptions,
  forumStore,
  getDefaultFilterLabelText = (code) => getUiCopy({
    surface: 'discussion-list-default-filter-label',
    code,
  })?.text || code,
  getDiscussionEmptyState = getEmptyState,
  getDiscussionForumNavItems = getForumNavItems,
  getDiscussionLoadingState = getStateBlock,
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
  const normalizedTags = computed(() => unwrapList(tags.value).map(normalizeTag))
  const flatTags = computed(() => flattenTags(tags.value))
  const currentTagContextParent = computed(() => findDiscussionListSidebarContextParent(currentTagSlug.value, normalizedTags.value))
  const sidebarPrimaryTagItems = computed(() => buildDiscussionListPrimaryTagItems(flatTags.value, currentTagContextParent.value))
  const sidebarSecondaryTagItems = computed(() => buildDiscussionListSecondaryTagItems(flatTags.value))
  const sidebarFilterItems = computed(() => buildSidebarFilterItems())
  const hasSidebarTagNavigation = computed(() => tags.value.length > 0)
  const showMoreTagsLink = computed(() => sidebarSecondaryTagItems.value.length > 0)
  const startDiscussionButtonStyle = computed(() => getDiscussionListStartButtonStyle(currentTag.value))
  const emptyStateText = computed(() => {
    const emptyState = getDiscussionEmptyState({
      surface: 'discussion-list-empty',
      isFollowingPage: isFollowingPage.value,
      listFilter: listFilter.value,
      currentTag: currentTag.value,
    })

    return emptyState?.text || '暂无讨论。'
  })
  const loadingStateText = computed(() => {
    const stateBlock = getDiscussionLoadingState({
      surface: 'discussion-list-loading',
      loading: true,
      listFilter: listFilter.value,
      currentTag: currentTag.value,
    })

    return stateBlock?.text || '正在加载讨论...'
  })

  function buildSidebarFilterItems() {
    const navItems = getDiscussionForumNavItems({
      authStore,
      forumStore,
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
      .filter(item => item.sidebar_visible !== false)
      .map(item => {
        const fallback = fallbackByCode.get(item.code) || {}
        const navItem = navItemsByCode.get(item.code) || {}
        const fallbackLabel = getDefaultFilterLabelText(item.code)
        return {
          ...fallback,
          ...navItem,
          ...item,
          label: item.label || navItem.label || fallback.label || fallbackLabel,
          icon: item.icon || navItem.icon || fallback.icon || 'far fa-comments',
        }
      })
      .filter(item => !(item.requires_authenticated_user && !authStore.user))
      .map(item => ({
        ...item,
        to: item.to || buildDiscussionFilterLocation(item),
        active: isDiscussionFilterActive({
          currentTagSlug: currentTagSlug.value,
          routeName: route.name,
          isFollowingPage: isFollowingPage.value,
          listFilter: listFilter.value,
          filterCode: item.code,
        }),
      }))
  }

  function getSidebarTagStyle(tag) {
    return {
      '--tag-color': tag.color || '#6c7a89'
    }
  }

  function isSidebarTagActive(tag) {
    return isDiscussionSidebarTagActive({
      currentTag: currentTag.value,
      currentTagSlug: currentTagSlug.value,
      normalizedTags: normalizedTags.value,
      tag,
    })
  }

  return {
    emptyStateText,
    loadingStateText,
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

export function useDiscussionListNavigation(options) {
  return createDiscussionListNavigation(options)
}
