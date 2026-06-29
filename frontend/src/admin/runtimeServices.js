import { requireFrontendService } from '../common/services.js'

export function requireAuthService() {
  return requireFrontendService('users.auth')
}

export function getAuthStore() {
  return requireAuthService().store()
}
