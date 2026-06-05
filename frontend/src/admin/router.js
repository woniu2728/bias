import { createRouter, createWebHashHistory } from 'vue-router'
import { findAdminRouteByPath, getAdminRoutes } from './registry'
import { bootstrapEnabledAdminExtensions } from './extensionBootstrap'
import { getRuntimeApplication } from '../common/applicationRegistry'
import { useAdminRegistryStore } from '../stores/adminRegistry'

const routes = [
  {
    path: '/',
    redirect: '/admin',
  },
  ...getAdminRoutes().map(route => ({
    path: route.path,
    name: route.name,
    component: route.component,
    redirect: route.redirect,
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

router.beforeEach(async (to) => {
  if (!to.path.startsWith('/admin')) {
    return true
  }

  const adminRegistryStore = useAdminRegistryStore()
  await adminRegistryStore.fetchExtensions()
  const bootstrapResult = await bootstrapEnabledAdminExtensions({
    app: getRuntimeApplication('admin'),
    extensions: adminRegistryStore.extensions,
    router,
    runtime: adminRegistryStore.extensionRuntime,
  })

  if (bootstrapResult.addedRouteCount > 0 && !to.name) {
    return to.fullPath
  }

  const route = findAdminRouteByPath(to.path, {
    isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
  })

  if (!route) {
    return '/admin'
  }

  return true
})

export default router
