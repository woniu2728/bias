
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

export function createDiscussionListSidebarState({
  authStore,
  getText = getUiCopy,
}) {
  const showStartDiscussionButton = computed(() => {
    if (authStore.value?.isRestoringSession && authStore.value?.isAuthenticated && !authStore.value?.user) {
      return false
    }

    return !authStore.value?.isAuthenticated || authStore.value?.canStartDiscussion
  })

  const showProfileLink = computed(() => Boolean(authStore.value?.user))

  const profileLinkLabel = computed(() => getText({
    surface: 'discussion-list-sidebar-profile-link',
  })?.text || '我的主页')

  return {
    profileLinkLabel,
    showProfileLink,
    showStartDiscussionButton,
  }
}

export function useDiscussionListSidebarState(options) {
  return createDiscussionListSidebarState(options)
}
