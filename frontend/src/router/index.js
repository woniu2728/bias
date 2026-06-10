import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore, openForgotPasswordModal, openLoginModal, openRegisterModal } from '@bias/users'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/discussions',
      redirect: '/'
    },
    {
      path: '/discussions/:id',
      redirect: to => `/d/${to.params.id}`
    }
  ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const hasActivePageContext = from.matched.length > 0

  if (['login', 'register', 'forgot-password'].includes(String(to.name || '')) && hasActivePageContext) {
    const redirectPath = typeof to.query.redirect === 'string' ? to.query.redirect : from.fullPath

    if (to.name === 'register') {
      openRegisterModal({ redirectPath })
    } else if (to.name === 'forgot-password') {
      openForgotPasswordModal({ redirectPath })
    } else {
      openLoginModal({ redirectPath })
    }

    next(false)
    return
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    if (hasActivePageContext) {
      openLoginModal({ redirectPath: to.fullPath })
      next(false)
      return
    }

    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  next()
})

export default router
