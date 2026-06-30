import { createRouter, createWebHistory } from 'vue-router'
import {
  getAuthStore,
  openForgotPassword,
  openLogin,
  openRegister,
} from '@/forum/runtimeServices'
import { resolveForumRouteGuard } from './guards.js'

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
router.beforeEach(async (to, from, next) => {
  const result = await resolveForumRouteGuard({
    to,
    from,
    authStore: getAuthStore(),
    openForgotPassword,
    openLogin,
    openRegister,
  })

  next(result === true ? undefined : result)
})

export default router
