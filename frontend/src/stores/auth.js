import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))

  const isAuthenticated = computed(() => !!accessToken.value)

  // 登录
  async function login(identification, password) {
    try {
      const data = await api.post('/users/login', {
        identification,
        password
      })

      accessToken.value = data.access
      refreshToken.value = data.refresh

      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)

      await fetchUser()

      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.error || '登录失败'
      }
    }
  }

  // 注册
  async function register(username, email, password) {
    try {
      await api.post('/users/register', {
        username,
        email,
        password
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
    user.value = null
    accessToken.value = null
    refreshToken.value = null

    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  // 获取当前用户信息
  async function fetchUser() {
    try {
      const data = await api.get('/users/me')
      user.value = data
      return data
    } catch (error) {
      user.value = null
      if (error.response?.status !== 503) {
        console.error('获取用户信息失败:', error)
      }
      return null
    }
  }

  // 检查认证状态
  async function checkAuth() {
    if (accessToken.value) {
      return fetchUser()
    }
    return null
  }

  return {
    user,
    isAuthenticated,
    login,
    register,
    logout,
    fetchUser,
    checkAuth
  }
})
