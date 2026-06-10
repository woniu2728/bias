import { computed } from '@bias/core'

export function createProfileViewBindings({
  activeTab,
  activePanel,
  avatarInput,
  avatarUploading,
  formatJoinDate,
  formatLastSeen,
  getUserAvatarColor,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
  handleAvatarSelected,
  isOnline,
  isOwnProfile,
  profilePanels,
  switchTab,
  user,
  userBadges,
}) {
  const heroBindings = computed(() => ({
    user: user.value,
    userBadges: userBadges.value,
    isOwnProfile: isOwnProfile.value,
    isOnline: isOnline.value,
    avatarUploading: avatarUploading.value,
    avatarInputRef: avatarInput.value,
    formatJoinDate,
    formatLastSeen,
    getUserAvatarColor,
    getUserPrimaryGroupIcon,
    getUserPrimaryGroupColor,
    getUserPrimaryGroupLabel,
  }))

  const heroEvents = {
    avatarSelected: handleAvatarSelected,
    openSettings() {
      switchTab('settings')
    },
  }

  const sidebarBindings = computed(() => ({
    activeTab: activeTab.value,
    items: profilePanels.value,
  }))

  const sidebarEvents = {
    changeTab: switchTab,
  }

  const activePanelComponent = computed(() => activePanel.value?.component || null)
  const activePanelProps = computed(() => activePanel.value?.componentProps || {})
  const activePanelEvents = computed(() => activePanel.value?.componentEvents || {})

  return {
    activePanelComponent,
    activePanelEvents,
    activePanelProps,
    heroBindings,
    heroEvents,
    sidebarBindings,
    sidebarEvents,
  }
}

export function useProfileViewBindings(options) {
  return createProfileViewBindings(options)
}
