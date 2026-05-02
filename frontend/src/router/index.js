import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { openForgotPasswordModal, openLoginModal, openRegisterModal } from '@/utils/authModal'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/DiscussionListView.vue'),
      meta: {
        title: '全部讨论',
        description: '浏览论坛最新讨论、热门主题和社区回复。'
      }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/AuthRouteView.vue')
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/AuthRouteView.vue')
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('@/views/AuthRouteView.vue')
    },
    {
      path: '/verify-email',
      name: 'verify-email',
      component: () => import('@/views/VerifyEmailView.vue')
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('@/views/ResetPasswordView.vue')
    },
    {
      path: '/discussions',
      redirect: '/'
    },
    {
      path: '/d/:id',
      name: 'discussion-detail',
      component: () => import('@/views/DiscussionDetailView.vue')
    },
    {
      path: '/discussions/:id',
      redirect: to => `/d/${to.params.id}`
    },
    {
      path: '/discussions/create',
      name: 'discussion-create',
      component: () => import('@/views/DiscussionCreateView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/SearchResultsView.vue'),
      meta: {
        title: '搜索',
        description: '搜索论坛中的讨论、回复和用户。'
      }
    },
    {
      path: '/following',
      name: 'following',
      component: () => import('@/views/DiscussionListView.vue'),
      meta: {
        requiresAuth: true,
        title: '关注的讨论',
        description: '查看你关注的讨论和最新回复。'
      }
    },
    {
      path: '/tags',
      name: 'tags',
      component: () => import('@/views/TagsView.vue'),
      meta: {
        title: '全部标签',
        description: '浏览论坛标签，按主题发现相关讨论。'
      }
    },
    {
      path: '/t/:slug',
      name: 'tag-detail',
      component: () => import('@/views/DiscussionListView.vue'),
      meta: {
        title: '标签讨论',
        description: '查看该标签下的论坛讨论。'
      }
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/u/:id',
      name: 'user-profile',
      component: () => import('@/views/ProfileView.vue')
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/views/NotificationView.vue'),
      meta: {
        requiresAuth: true,
        title: '通知',
        description: '查看你的论坛通知、回复提醒和系统消息。'
      }
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
