
import { getUserAvatarColor, useOnlineUsersStore } from '@bias/users'
import { useProfilePage } from './useProfilePage'
import { useProfileMetaState } from './useProfileMetaState'
import { useProfilePanelState } from './useProfilePanelState'
import { useProfilePresentation } from './useProfilePresentation'
import { useProfileViewBindings } from './useProfileViewBindings'

export function useProfileViewModel({
  authStore,
  forumStore,
  modalStore,
  pageState: injectedPageState,
  route,
  router,
}) {
  const onlineUsersStore = useOnlineUsersStore()
  const pageState = injectedPageState || useProfilePage({
    authStore,
    modalStore,
    route,
    router,
  })
  const presentationState = useProfilePresentation(pageState.user, {
    isUserOnline: onlineUsersStore.isUserOnline,
  })
  const metaState = useProfileMetaState({
    authStore,
    forumStore,
    loading: pageState.loading,
    user: pageState.user,
  })
  const panelState = useProfilePanelState({
    authStore,
    formatDate: presentationState.formatDate,
    forumStore,
    pageState,
  })
  const viewBindings = useProfileViewBindings({
    activeTab: pageState.activeTab,
    activePanel: panelState.activePanel,
    avatarInput: pageState.avatarInput,
    avatarUploading: pageState.avatarUploading,
    formatJoinDate: presentationState.formatJoinDate,
    formatLastSeen: presentationState.formatLastSeen,
    getUserAvatarColor,
    getUserPrimaryGroupColor: presentationState.getUserPrimaryGroupColor,
    getUserPrimaryGroupIcon: presentationState.getUserPrimaryGroupIcon,
    getUserPrimaryGroupLabel: presentationState.getUserPrimaryGroupLabel,
    handleAvatarSelected: pageState.handleAvatarSelected,
    isOnline: presentationState.isOnline,
    isOwnProfile: pageState.isOwnProfile,
    profilePanels: panelState.profilePanels,
    switchTab: pageState.switchTab,
    user: pageState.user,
    userBadges: metaState.userBadges,
  })

  return {
    ...pageState,
    ...metaState,
    ...presentationState,
    ...panelState,
    ...viewBindings,
    getUserAvatarColor,
  }
}
