import { getFrontendService, requireFrontendService } from '../common/services.js'

const noopConnectionStore = {
  connectionFailureCount: { value: 0 },
  hasConnectionError: { value: false },
  isConnected: { value: false },
  isReconnecting: { value: false },
  connect() {},
  disconnect() {},
  reconnect() {},
}

export function getAuthService() {
  return getFrontendService('users.auth')
}

export function requireAuthService() {
  return requireFrontendService('users.auth')
}

export function getAuthStore() {
  return requireAuthService().store()
}

export function openLogin(options = {}) {
  return requireAuthService().openLogin(options)
}

export function openRegister(options = {}) {
  return requireAuthService().openRegister(options)
}

export function openForgotPassword(options = {}) {
  return requireAuthService().openForgotPassword(options)
}

export function getOnlineUsersService() {
  return getFrontendService('users.online')
}

export function getOnlineUsersStore() {
  return getOnlineUsersService()?.store?.() || noopConnectionStore
}

export function getForumRealtimeService() {
  return getFrontendService('realtime.forum')
}

export function getForumRealtimeStore() {
  return getForumRealtimeService()?.store?.() || noopConnectionStore
}
