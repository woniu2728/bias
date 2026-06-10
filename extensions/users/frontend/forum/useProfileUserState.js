import {
  api,
  ref,
  computed } from '@bias/core'

function normalizeUserIdentifier(value) {
  return String(value || '')
}

function isNumericIdentifier(value) {
  return /^\d+$/.test(normalizeUserIdentifier(value))
}

export function createProfileUserState({
  activeTab,
  apiClient = api,
  authStore,
  getLoadUserErrorText,
  getProfileErrorMessage,
  loadPreferences,
  markPostsRequestedForCurrentUser,
  normalizeUser,
  resourceStore,
  route,
  setEditForm,
  setLoading,
  setSettingsError,
  setVerificationError,
  setVerificationSuccess,
  userId,
}) {
  const user = computed(() => (userId.value ? resourceStore.get('users', userId.value) : null))
  const loading = ref(true)
  const isOwnProfile = computed(() => authStore.user && user.value && authStore.user.id === user.value.id)

  function resetUserScope() {
    userId.value = null
  }

  async function loadUser() {
    setLoading(true)

    try {
      let data
      if (route.params.id) {
        const identifier = normalizeUserIdentifier(route.params.id)
        data = isNumericIdentifier(identifier)
          ? await apiClient.get(`/users/${identifier}`)
          : await apiClient.get(`/users/by-username/${encodeURIComponent(identifier)}`)
      } else {
        data = await apiClient.get('/users/me')
      }

      const normalizedUser = resourceStore.upsert('users', normalizeUser(data))
      userId.value = normalizedUser.id
      if (activeTab.value === 'posts') {
        markPostsRequestedForCurrentUser()
      }

      setEditForm({
        display_name: normalizedUser.display_name || '',
        bio: normalizedUser.bio || '',
        email: normalizedUser.email || '',
      })

      if (!authStore.user || authStore.user.id !== normalizedUser.id) {
        setVerificationSuccess('')
        setVerificationError('')
      }
    } catch (error) {
      console.error('加载用户失败:', error)
      setSettingsError(getProfileErrorMessage(
        error,
        getLoadUserErrorText()
      ))
    } finally {
      setLoading(false)
    }
  }

  async function refreshProfile() {
    await loadUser()
    if (isOwnProfile.value) {
      await loadPreferences()
    }
  }

  return {
    isOwnProfile,
    loadUser,
    loading,
    refreshProfile,
    resetUserScope,
    user,
  }
}

export function useProfileUserState({
  activeTab,
  authStore,
  getLoadUserErrorText,
  getProfileErrorMessage,
  loadPreferences,
  markPostsRequestedForCurrentUser,
  normalizeUser,
  resourceStore,
  route,
  setEditForm,
  setSettingsError,
  setVerificationError,
  setVerificationSuccess,
}) {
  const userId = ref(null)
  const loading = ref(true)

  const state = createProfileUserState({
    activeTab,
    apiClient: api,
    authStore,
    getLoadUserErrorText,
    getProfileErrorMessage,
    loadPreferences,
    markPostsRequestedForCurrentUser,
    normalizeUser,
    resourceStore,
    route,
    setEditForm,
    setLoading(value) {
      loading.value = value
    },
    setSettingsError,
    setVerificationError,
    setVerificationSuccess,
    userId,
  })

  return {
    ...state,
    loading,
    userId,
  }
}
