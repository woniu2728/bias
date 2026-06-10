
import {
  computed } from '@bias/core'
import { getEmptyState,
  getForumNavItems,
  getForumSidebarSections,
  getStateBlock,
  getUiCopy
} from '@bias/forum'
import {
  buildDiscussionFilterLocation,
  getDiscussionListStartButtonStyle,
  isDiscussionFilterActive,
} from './discussionListNavigation.js'

const DEFAULT_DISCUSSION_FILTERS = [
  { code: 'all', icon: 'far fa-comments', sidebar_visible: true, route_path: '/' },
]

export function createDiscussionListNavigation({
  authStore,
  contextSubject,
  contextSubjectKey,
  discussionListContextData,
  discussionListContexts,
  filterOptions,
  forumStore,
  getDefaultFilterLabelText = (code) => getUiCopy({
    surface: 'discussion-list-default-filter-label',
    code,
  })?.text || code,
  getDiscussionEmptyState = getEmptyState,
  getDiscussionForumNavItems = getForumNavItems,
  getDiscussionSidebarSections = getForumSidebarSections,
  getDiscussionLoadingState = getStateBlock,
  isFollowingPage,
  listFilter,
  route,
}) {
  const isTagsPage = computed(() => route.name === 'tags')
  const isAllDiscussionsPage = computed(() => route.name === 'home' && !contextSubjectKey.value)
  const isOwnProfilePage = computed(() => {
    if (!authStore.user) return false

    return (
      route.name === 'profile'
      || (route.name === 'user-profile' && String(route.params.id) === String(authStore.user.id))
    )
  })
  const activeDiscussionListContexts = computed(() => Array.isArray(discussionListContexts?.value)
    ? discussionListContexts.value
    : [])
  const activeDiscussionListContextData = computed(() => discussionListContextData?.value || {})
  const sidebarFilterItems = computed(() => buildSidebarFilterItems())
  const sidebarExtensionSections = computed(() => getDiscussionSidebarSections({
    authStore,
    contexts: activeDiscussionListContexts.value,
    contextSubject: contextSubject.value,
    contextSubjectKey: contextSubjectKey.value,
    discussionListContextData: activeDiscussionListContextData.value,
    forumStore,
    isTagsPage: isTagsPage.value,
    route,
    surface: 'discussion-sidebar',
  }))
  const startDiscussionButtonStyle = computed(() => getDiscussionListStartButtonStyle(contextSubject.value))
  const emptyStateText = computed(() => {
    const emptyState = getDiscussionEmptyState({
      surface: 'discussion-list-empty',
      isFollowingPage: isFollowingPage.value,
      listFilter: listFilter.value,
      contextSubject: contextSubject.value,
    })

    return emptyState?.text || '暂无讨论。'
  })
  const loadingStateText = computed(() => {
    const stateBlock = getDiscussionLoadingState({
      surface: 'discussion-list-loading',
      loading: true,
      listFilter: listFilter.value,
      contextSubject: contextSubject.value,
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
          contextSubjectKey: contextSubjectKey.value,
          routeName: route.name,
          isFollowingPage: isFollowingPage.value,
          listFilter: listFilter.value,
          filterCode: item.code,
        }),
      }))
  }

  return {
    emptyStateText,
    loadingStateText,
    isAllDiscussionsPage,
    isOwnProfilePage,
    isTagsPage,
    sidebarFilterItems,
    sidebarExtensionSections,
    startDiscussionButtonStyle
  }
}

export function useDiscussionListNavigation(options) {
  return createDiscussionListNavigation(options)
}
