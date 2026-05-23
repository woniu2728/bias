import api from '@/api'
import { getUiCopy } from '@/forum/registry'
import { useProfileAccountActions } from '@/composables/useProfileAccountActions'
import { useProfileAccountState } from '@/composables/useProfileAccountState'
import { useProfileContentState } from '@/composables/useProfileContentState'
import { useProfilePageActions } from '@/composables/useProfilePageActions'
import { useProfilePageLifecycle } from '@/composables/useProfilePageLifecycle'
import { useProfileRealtimeState } from '@/composables/useProfileRealtimeState'
import { useProfileUserState } from '@/composables/useProfileUserState'
import { useForumRealtimeStore } from '@/stores/forumRealtime'
import { useForumUiStore } from '@/stores/forumUi'
import { useResourceStore } from '@/stores/resource'
import { normalizeUser } from '@/utils/forum'
import { useProfileRouteState } from './useProfileRouteState'

export function useProfilePage({
  authStore,
  modalStore,
  route,
  router
}) {
  const resourceStore = useResourceStore()
  const forumRealtimeStore = useForumRealtimeStore()
  const forumUiStore = useForumUiStore()
  const routeState = useProfileRouteState({ route, router })
  const accountState = useProfileAccountState()

  const activeTab = routeState.activeTab
  function getProfileUiCopy(surface, context = {}, fallback = '') {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  function getProfileErrorMessage(error, fallback = getProfileUiCopy('profile-error-unknown', {}, '未知错误')) {
    return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
  }
  const profileUserState = useProfileUserState({
    activeTab,
    authStore,
    getLoadUserErrorText() {
      return getProfileUiCopy('profile-settings-load-error', {}, '加载用户失败，请稍后重试')
    },
    getProfileErrorMessage,
    loadPreferences() {
      return profileAccountActions.loadPreferences()
    },
    markPostsRequestedForCurrentUser() {
      profileContentState.markPostsRequestedForCurrentUser()
    },
    normalizeUser,
    resourceStore,
    route,
    setEditForm(payload) {
      accountState.editForm.value = payload
    },
    setSettingsError(message) {
      accountState.settingsError.value = message
    },
    setVerificationError(message) {
      accountState.verificationError.value = message
    },
    setVerificationSuccess(message) {
      accountState.verificationSuccess.value = message
    },
  })
  const profileContentState = useProfileContentState({
    activeTab,
    forumRealtimeStore,
    getErrorMessage: getProfileErrorMessage,
    getLoadDiscussionsErrorText() {
      return getProfileUiCopy('profile-discussions-load-error', {}, '加载讨论失败，请稍后重试')
    },
    getLoadPostsErrorText() {
      return getProfileUiCopy('profile-posts-load-error', {}, '加载回复失败，请稍后重试')
    },
    getUser() {
      return profileUserState.user.value
    },
    resourceStore,
    setSettingsError(message) {
      accountState.settingsError.value = message
    },
    userId: profileUserState.userId,
  })
  const profileRealtimeState = useProfileRealtimeState({
    activeTab,
    contentState: profileContentState,
    resourceStore,
    userId: profileUserState.userId,
  })

  function addForumEventListener() {
    if (typeof window === 'undefined') return
    window.addEventListener('bias:forum-event', profileRealtimeState.handleForumEvent)
  }

  function removeForumEventListener() {
    if (typeof window === 'undefined') return
    window.removeEventListener('bias:forum-event', profileRealtimeState.handleForumEvent)
  }

  function cleanupTrackedDiscussions() {
    profileContentState.cleanupTrackedDiscussions()
  }

  function resetProfileScope() {
    profileUserState.resetUserScope()
    profileContentState.resetProfileScope()
  }

  useProfilePageLifecycle({
    addForumEventListener,
    cleanupTrackedDiscussions,
    refreshProfile: profileUserState.refreshProfile,
    removeForumEventListener,
    resetProfileScope,
    route,
  })
  const profilePageActions = useProfilePageActions({
    activeTab,
    markPostsRequestedForCurrentUser() {
      profileContentState.markPostsRequestedForCurrentUser()
    },
    pushRouteState(payload) {
      return routeState.push(payload)
    },
    userId: profileUserState.userId,
  })

  const profileAccountActions = useProfileAccountActions({
    apiClient: api,
    authStore,
    avatarInput: accountState.avatarInput,
    avatarUploading: accountState.avatarUploading,
    changingPassword: accountState.changingPassword,
    editForm: accountState.editForm,
    forumUiStore,
    getProfileErrorMessage,
    getProfileUiCopy,
    loadingPreferences: accountState.loadingPreferences,
    modalStore,
    passwordError: accountState.passwordError,
    passwordForm: accountState.passwordForm,
    passwordSuccess: accountState.passwordSuccess,
    preferences: accountState.preferences,
    preferencesError: accountState.preferencesError,
    preferencesSuccess: accountState.preferencesSuccess,
    resourceStore,
    saving: accountState.saving,
    savingPreferences: accountState.savingPreferences,
    settingsError: accountState.settingsError,
    settingsSuccess: accountState.settingsSuccess,
    user: profileUserState.user,
    userId: profileUserState.userId,
    verificationError: accountState.verificationError,
    verificationSending: accountState.verificationSending,
    verificationSuccess: accountState.verificationSuccess,
    normalizeUser,
  })

  return {
    user: profileUserState.user,
    discussions: profileContentState.discussions,
    posts: profileContentState.posts,
    loading: profileUserState.loading,
    loadingDiscussions: profileContentState.loadingDiscussions,
    loadingPosts: profileContentState.loadingPosts,
    activeTab,
    saving: accountState.saving,
    avatarUploading: accountState.avatarUploading,
    avatarInput: accountState.avatarInput,
    settingsSuccess: accountState.settingsSuccess,
    settingsError: accountState.settingsError,
    verificationSending: accountState.verificationSending,
    verificationSuccess: accountState.verificationSuccess,
    verificationError: accountState.verificationError,
    changingPassword: accountState.changingPassword,
    passwordSuccess: accountState.passwordSuccess,
    passwordError: accountState.passwordError,
    loadingPreferences: accountState.loadingPreferences,
    savingPreferences: accountState.savingPreferences,
    preferencesSuccess: accountState.preferencesSuccess,
    preferencesError: accountState.preferencesError,
    editForm: accountState.editForm,
    passwordForm: accountState.passwordForm,
    preferences: accountState.preferences,
    isOwnProfile: profileUserState.isOwnProfile,
    switchTab: profilePageActions.switchTab,
    saveProfile: profileAccountActions.saveProfile,
    savePreferences: profileAccountActions.savePreferences,
    resendVerificationEmail: profileAccountActions.resendVerificationEmail,
    changePassword: profileAccountActions.changePassword,
    handleAvatarSelected: profileAccountActions.handleAvatarSelected
  }
}
