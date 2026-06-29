import { createRouter, createWebHistory } from 'vue-router'
import {
  getAuthStore,
  openForgotPassword,
  openLogin,
  openRegister,
} from '@/forum/runtimeServices'

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
  const authStore = getAuthStore()
  const hasActivePageContext = from.matched.length > 0

  if (['login', 'register', 'forgot-password'].includes(String(to.name || '')) && hasActivePageContext) {
    const redirectPath = typeof to.query.redirect === 'string' ? to.query.redirect : from.fullPath

    if (to.name === 'register') {
      openRegister({ redirectPath })
    } else if (to.name === 'forgot-password') {
      openForgotPassword({ redirectPath })
    } else {
      openLogin({ redirectPath })
    }

    next(false)
    return
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    if (hasActivePageContext) {
      openLogin({ redirectPath: to.fullPath })
      next(false)
      return
    }

    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  next()
})

export default router
