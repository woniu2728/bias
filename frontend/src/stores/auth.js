import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))
  const isRestoringSession = ref(Boolean(accessToken.value))

  const isAuthenticated = computed(() => !!accessToken.value)
  const forumPermissions = computed(() => Array.isArray(user.value?.forum_permissions) ? user.value.forum_permissions : [])
  const canStartDiscussion = computed(() => hasPermission('startDiscussion'))

  // 登录
  async function login(identification, password, humanVerificationToken = '') {
    try {
      isRestoringSession.value = true
      const data = await api.post('/users/login', {
        identification,
        password,
        human_verification_token: humanVerificationToken || undefined
      })

      accessToken.value = data.access

      localStorage.setItem('access_token', data.access)
      localStorage.removeItem('refresh_token')

      await fetchUser()

      return { success: true }
    } catch (error) {
      isRestoringSession.value = false
      return {
        success: false,
        error: error.response?.data?.error || '登录失败'
      }
    }
  }

  // 注册
  async function register(username, email, password, humanVerificationToken = '') {
    try {
      await api.post('/users/register', {
        username,
        email,
        password,
        human_verification_token: humanVerificationToken || undefined
      })

      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.error || '注册失败'
      }
    }
  }

  // 登出
  function logout() {
    api.post('/users/logout', null, {
      skipAuthRefresh: true,
      skipAuthInvalidation: true
    }).catch(() => {})

    user.value = null
    accessToken.value = null
    isRestoringSession.value = false

    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  // 获取当前用户信息
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

  // 检查认证状态
  async function checkAuth() {
    if (accessToken.value) {
      isRestoringSession.value = true
      return fetchUser()
    }
    isRestoringSession.value = false
    return null
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
    checkAuth
  }
})
