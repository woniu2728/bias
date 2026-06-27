import { api, computed, defineStore, ref } from '@bias/core'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isRestoringSession = ref(true)

  const isAuthenticated = computed(() => !!user.value)
  const forumPermissions = computed(() => Array.isArray(user.value?.forum_permissions) ? user.value.forum_permissions : [])
  const canStartDiscussion = computed(() => hasPermission('startDiscussion'))

  async function login(identification, password, humanVerification = '') {
    try {
      isRestoringSession.value = true
      const challenge = normalizeHumanVerificationSubmission(humanVerification)
      await api.post('/users/login', {
        identification,
        password,
        ...challenge,
      })

      await fetchUser()

      return { success: true }
    } catch (error) {
      isRestoringSession.value = false
      return {
        success: false,
        error: error.response?.data?.error || '登录失败',
      }
    }
  }

  async function register(username, email, password, humanVerification = '') {
    try {
      const challenge = normalizeHumanVerificationSubmission(humanVerification)
      await api.post('/users/register', {
        username,
        email,
        password,
        ...challenge,
      })

      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.error || '注册失败',
      }
    }
  }

  function normalizeHumanVerificationSubmission(value = '') {
    if (value && typeof value === 'object') {
      return {
        human_verification_token: value.human_verification_token ?? value.token ?? undefined,
        human_verification_payload: value.human_verification_payload ?? value.payload ?? undefined,
      }
    }
    return {
      human_verification_token: value || undefined,
    }
  }

  function logout() {
    api.post('/users/logout', null, {
      skipAuthRefresh: true,
      skipAuthInvalidation: true,
    }).catch(() => {})

    user.value = null
    isRestoringSession.value = false
  }

  async function fetchUser() {
    try {
      const data = await api.get('/users/me')
      user.value = data
      isRestoringSession.value = false
      return data
    } catch (error) {
      if (error.response?.status === 401) {
        logout()
      } else {
        user.value = null
        isRestoringSession.value = false
      }
      if (error.response?.status !== 503) {
        console.error('获取用户信息失败:', error)
      }
      return null
    }
  }

  async function checkAuth() {
    isRestoringSession.value = true

    try {
      const session = await api.get('/users/session', {
        skipAuthRefresh: true,
        skipAuthInvalidation: true,
      })

      if (!session?.authenticated) {
        user.value = null
        isRestoringSession.value = false
        return null
      }

      user.value = session.user
      isRestoringSession.value = false
      return session.user
    } catch (error) {
      user.value = null
      isRestoringSession.value = false
      if (error.response?.status !== 503) {
        console.error('检查登录状态失败:', error)
      }
      return null
    }
  }

  function hasPermission(permission) {
    if (!isAuthenticated.value) return false
    if (user.value?.is_staff) return true
    return forumPermissions.value.includes(permission)
  }

  return {
    user,
    isAuthenticated,
    isRestoringSession,
    forumPermissions,
    canStartDiscussion,
    hasPermission,
    login,
    register,
    logout,
    fetchUser,
    checkAuth,
  }
})
