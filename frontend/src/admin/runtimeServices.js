import { reactive } from 'vue'
import api from '../api/index.js'
import { getFrontendService, requireFrontendService } from '../common/services.js'

const fallbackAuthStore = reactive({
  user: null,
  isAuthenticated: false,
  isRestoringSession: false,
  forumPermissions: [],
  canStartDiscussion: false,

  hasPermission(permission) {
    if (!this.isAuthenticated) return false
    if (this.user?.is_staff) return true
    return this.forumPermissions.includes(permission)
  },

  async checkAuth() {
    this.isRestoringSession = true
    try {
      const session = await api.get('/users/session', {
        skipAuthRefresh: true,
        skipAuthInvalidation: true,
      })
      this.user = session?.authenticated ? (session.user || null) : null
      this.isAuthenticated = !!this.user
      this.forumPermissions = Array.isArray(this.user?.forum_permissions) ? this.user.forum_permissions : []
      this.canStartDiscussion = this.hasPermission('startDiscussion')
      return this.user
    } catch {
      this.user = null
      this.isAuthenticated = false
      this.forumPermissions = []
      this.canStartDiscussion = false
      return null
    } finally {
      this.isRestoringSession = false
    }
  },

  logout() {
    api.post('/users/logout', null, {
      skipAuthRefresh: true,
      skipAuthInvalidation: true,
    }).catch(() => {})
    this.user = null
    this.isAuthenticated = false
    this.forumPermissions = []
    this.canStartDiscussion = false
    this.isRestoringSession = false
  },
})

export function requireAuthService() {
  return requireFrontendService('users.auth')
}

export function getAuthService() {
  return getFrontendService('users.auth')
}

export function getAuthStore() {
  return getAuthService()?.store?.() || fallbackAuthStore
}
