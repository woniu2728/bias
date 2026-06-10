import { computed, ref } from 'vue'
import { getUiCopy } from '@/forum/registry'

export function useHeaderMobileState({
  authStore,
  forumTitle,
  route
}) {
  const showMobileDrawer = ref(false)
  const mobileHeaderOverride = ref(null)

  const isOwnProfileRoute = computed(() => {
    if (!authStore.user) return false

    return route.name === 'profile'
      || (route.name === 'user-profile' && String(route.params.id) === String(authStore.user.id))
  })

  const mobilePageTitle = computed(() => {
    const listFilter = resolveMobileDiscussionListFilter(route)

    if (mobileHeaderOverride.value?.title) {
      return mobileHeaderOverride.value.title
    }

    return getUiCopy({
      surface: 'header-mobile-page-title',
      routeName: route.name,
      forumTitle,
      listFilter,
    })?.text || resolveMobilePageTitle(route.name, forumTitle, listFilter)
  })

  const mobileLeftActionIcon = computed(() => mobileHeaderOverride.value?.leftAction === 'back' ? 'fas fa-angle-left' : 'fas fa-bars')
  const mobileLeftActionLabel = computed(() => getUiCopy({
    surface: 'header-mobile-left-action-label',
    leftAction: mobileHeaderOverride.value?.leftAction || 'menu',
  })?.text || (mobileHeaderOverride.value?.leftAction === 'back' ? '返回上一页' : '打开导航菜单'))

  const mobileRightActionType = computed(() => {
    if (mobileHeaderOverride.value?.rightAction) {
      return mobileHeaderOverride.value.rightAction
    }

    return 'none'
  })

  const showMobileRightAction = computed(() => mobileRightActionType.value !== 'none')

  const mobileRightActionIcon = computed(() => {
    switch (mobileRightActionType.value) {
      case 'discussion-menu':
        return 'fas fa-ellipsis-v'
      case 'login':
        return 'fas fa-right-to-bracket'
      default:
        return 'fas fa-pen-to-square'
    }
  })

  const mobileRightActionLabel = computed(() => {
    return getUiCopy({
      surface: 'header-mobile-right-action-label',
      actionType: mobileRightActionType.value,
    })?.text || resolveMobileRightActionLabel(mobileRightActionType.value)
  })

  function isMobileNavActive(key) {
    if (key === 'home') {
      return route.name === 'home'
    }

    if (key === 'profile') {
      return isOwnProfileRoute.value
    }

    return route.name === key
  }

  function closeMobileDrawer() {
    showMobileDrawer.value = false
  }

  function flipMobileDrawer() {
    showMobileDrawer.value = !showMobileDrawer.value
  }

  function resetMobileHeaderOverride() {
    mobileHeaderOverride.value = null
  }

  function updateMobileHeaderOverride(detail) {
    mobileHeaderOverride.value = detail || null
  }

  return {
    showMobileDrawer,
    mobileHeaderOverride,
    isOwnProfileRoute,
    mobilePageTitle,
    mobileLeftActionIcon,
    mobileLeftActionLabel,
    mobileRightActionType,
    showMobileRightAction,
    mobileRightActionIcon,
    mobileRightActionLabel,
    isMobileNavActive,
    closeMobileDrawer,
    flipMobileDrawer,
    resetMobileHeaderOverride,
    updateMobileHeaderOverride
  }
}

function resolveMobilePageTitle(routeName, forumTitle, listFilter = 'all') {
  switch (routeName) {
    case 'home':
      return resolveDiscussionListFilterLabel(listFilter)
    case 'following':
      return resolveDiscussionListFilterLabel('following')
    case 'profile':
    case 'user-profile':
      return '个人主页'
    case 'search':
      return '搜索结果'
    case 'discussion-detail':
      return '讨论详情'
    case 'login':
      return '登录'
    case 'register':
      return '注册'
    default:
      return forumTitle || 'Bias'
  }
}

function resolveMobileDiscussionListFilter(route) {
  if (route?.name === 'following') return 'following'
  if (route?.name !== 'home') return 'all'
  return String(route?.query?.filter || 'all').trim() || 'all'
}

function resolveDiscussionListFilterLabel(filterCode) {
  switch (String(filterCode || 'all').trim()) {
    case 'following':
      return '关注中'
    case 'unread':
      return '未读'
    case 'my':
      return '我的讨论'
    default:
      return '全部讨论'
  }
}

function resolveMobileRightActionLabel(actionType) {
  switch (actionType) {
    case 'discussion-menu':
      return '讨论操作菜单'
    default:
      return ''
  }
}
