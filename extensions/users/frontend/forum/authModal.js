import { getAuthModalProvider } from './userFrontendRegistry.js'

function sanitizeRedirectPath(value) {
  const fallback = '/'
  const redirect = String(value || '').trim()

  if (!redirect || !redirect.startsWith('/')) {
    return fallback
  }

  if (['/login', '/register', '/forgot-password'].includes(redirect)) {
    return fallback
  }

  return redirect
}

function showAuthModal(mode, options = {}) {
  const provider = getAuthModalProvider({
    mode,
    options,
    redirectPath: sanitizeRedirectPath(options.redirectPath),
  })

  if (!provider || typeof provider.open !== 'function') {
    return null
  }

  return provider.open({
    mode,
    redirectPath: sanitizeRedirectPath(options.redirectPath),
    initialIdentification: options.initialIdentification || '',
    initialEmail: options.initialEmail || '',
    initialUsername: options.initialUsername || '',
    initialPassword: options.initialPassword || '',
  })
}

export function openLoginModal(options = {}) {
  return showAuthModal('login', options)
}

export function openRegisterModal(options = {}) {
  return showAuthModal('register', options)
}

export function openForgotPasswordModal(options = {}) {
  return showAuthModal('forgot-password', options)
}

export { sanitizeRedirectPath }
