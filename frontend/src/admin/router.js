import { createRouter, createWebHashHistory } from 'vue-router'
import { getAdminRoutes } from './registry'

const routes = [
  {
    path: '/',
    redirect: '/admin',
  },
  ...getAdminRoutes().map(route => ({
    path: route.path,
    name: route.name,
    component: route.component,
  })),
  {
    path: '/:pathMatch(.*)*',
    redirect: '/admin',
  },
]

const router = createRouter({
  // Admin SPA is served from admin.html, so hash history avoids broken deep links
  // when navigating out to the forum and using the browser back button.
  history: createWebHashHistory(),
  routes,
})

export default router
