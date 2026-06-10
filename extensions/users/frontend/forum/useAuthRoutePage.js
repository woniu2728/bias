import { onMounted } from '@bias/core'

export function resolveAuthRouteMode(routeName) {
  if (routeName === 'register') return 'register'
  if (routeName === 'forgot-password') return 'forgot-password'
  return 'login'
}

export function createAuthRoutePage({
  openForgotPassword,
  openLogin,
  openRegister,
  route,
  router,
  sanitizeRedirectPath = value => {
    const fallback = '/'
    const redirect = String(value || '').trim()

    if (!redirect || !redirect.startsWith('/')) {
      return fallback
    }

    if (['/login', '/register', '/forgot-password'].includes(redirect)) {
      return fallback
    }

    return redirect
  },
}) {
  const redirectPath = sanitizeRedirectPath(
    typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  )
  const mode = resolveAuthRouteMode(route.name)

  function openAuthModal() {
    if (mode === 'register') {
      openRegister({ redirectPath })
      return
    }

    if (mode === 'forgot-password') {
      openForgotPassword({ redirectPath })
      return
    }

    openLogin({ redirectPath })
  }

  function finalizeRedirect() {
    router.replace('/')
  }

  function run() {
    openAuthModal()
    finalizeRedirect()
  }

  return {
    finalizeRedirect,
    mode,
    openAuthModal,
    redirectPath,
    run,
  }
}

export function useAuthRoutePage(options) {
  const page = createAuthRoutePage(options)

  onMounted(() => {
    page.run()
  })

  return page
}
