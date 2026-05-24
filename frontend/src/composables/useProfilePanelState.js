import { computed, watch } from 'vue'
import { getProfilePanels } from '../forum/frontendRegistry.js'

function defaultBuildDiscussionPath(discussionOrId) {
  const id = typeof discussionOrId === 'object' ? discussionOrId?.id : discussionOrId
  return `/d/${id}`
}

export function createProfilePanelState({
  authStore,
  formatDate,
  forumStore,
  getPanels = getProfilePanels,
  getDiscussionPath = defaultBuildDiscussionPath,
  pageState,
}) {
  const profilePanels = computed(() => {
    if (!pageState.user.value) return []

    return getPanels({
      authStore,
      forumStore,
      user: pageState.user.value,
      discussions: pageState.discussions.value,
      posts: pageState.posts.value,
      loadingDiscussions: pageState.loadingDiscussions.value,
      loadingPosts: pageState.loadingPosts.value,
      isOwnProfile: pageState.isOwnProfile.value,
      buildDiscussionPath: getDiscussionPath,
      formatDate,
      editForm: pageState.editForm.value,
      preferences: pageState.preferences.value,
      saving: pageState.saving.value,
      settingsSuccess: pageState.settingsSuccess.value,
      settingsError: pageState.settingsError.value,
      loadingPreferences: pageState.loadingPreferences.value,
      savingPreferences: pageState.savingPreferences.value,
      preferencesSuccess: pageState.preferencesSuccess.value,
      preferencesError: pageState.preferencesError.value,
      saveProfile: pageState.saveProfile,
      savePreferences: pageState.savePreferences,
      passwordForm: pageState.passwordForm.value,
      verificationSending: pageState.verificationSending.value,
      verificationSuccess: pageState.verificationSuccess.value,
      verificationError: pageState.verificationError.value,
      resendVerificationEmail: pageState.resendVerificationEmail,
      changingPassword: pageState.changingPassword.value,
      passwordSuccess: pageState.passwordSuccess.value,
      passwordError: pageState.passwordError.value,
      changePassword: pageState.changePassword,
    })
  })

  const activePanel = computed(() => {
    return profilePanels.value.find(item => item.key === pageState.activeTab.value) || profilePanels.value[0] || null
  })

  watch(
    profilePanels,
    value => {
      if (!value.length) return
      if (!value.some(item => item.key === pageState.activeTab.value)) {
        pageState.switchTab(value[0].key)
      }
    },
    { immediate: true }
  )

  function handleEditFormUpdate({ key, value }) {
    if (!pageState.editForm.value || !key) return
    pageState.editForm.value = {
      ...pageState.editForm.value,
      [key]: value,
    }
  }

  function handlePasswordFormUpdate({ key, value }) {
    if (!pageState.passwordForm.value || !key) return
    pageState.passwordForm.value = {
      ...pageState.passwordForm.value,
      [key]: value,
    }
  }

  function handlePreferenceUpdate({ key, value }) {
    if (!pageState.preferences.value || !key) return
    pageState.preferences.value = {
      ...pageState.preferences.value,
      values: {
        ...(pageState.preferences.value.values || {}),
        [key]: Boolean(value),
      },
    }
  }

  return {
    activePanel,
    handleEditFormUpdate,
    handlePasswordFormUpdate,
    handlePreferenceUpdate,
    profilePanels,
  }
}

export function useProfilePanelState(options) {
  return createProfilePanelState(options)
}
