export async function resolveForumRouteGuard({
  to,
  from,
  authStore,
  openForgotPassword,
  openLogin,
  openRegister,
}) {
  const hasActivePageContext = Array.isArray(from?.matched) && from.matched.length > 0
  const routeName = String(to?.name || '')

  if (['login', 'register', 'forgot-password'].includes(routeName) && hasActivePageContext) {
    const redirectPath = typeof to.query?.redirect === 'string' ? to.query.redirect : from.fullPath

    if (routeName === 'register') {
      openRegister?.({ redirectPath })
    } else if (routeName === 'forgot-password') {
      openForgotPassword?.({ redirectPath })
    } else {
      openLogin?.({ redirectPath })
    }

    return false
  }

  if (to?.meta?.requiresAuth && authStore?.isRestoringSession && typeof authStore.checkAuth === 'function') {
    await authStore.checkAuth()
  }

  if (to?.meta?.requiresAuth && !authStore?.isAuthenticated) {
    if (hasActivePageContext) {
      openLogin?.({ redirectPath: to.fullPath })
      return false
    }

    return { name: 'login', query: { redirect: to.fullPath } }
  }

  return true
}
