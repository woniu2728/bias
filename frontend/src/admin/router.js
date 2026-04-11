import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardPage from './views/DashboardPage.vue'
import BasicsPage from './views/BasicsPage.vue'
import PermissionsPage from './views/PermissionsPage.vue'
import UsersPage from './views/UsersPage.vue'
import FlagsPage from './views/FlagsPage.vue'
import AppearancePage from './views/AppearancePage.vue'
import TagsPage from './views/TagsPage.vue'
import MailPage from './views/MailPage.vue'
import AdvancedPage from './views/AdvancedPage.vue'

const routes = [
  {
    path: '/',
    redirect: '/admin',
  },
  {
    path: '/admin',
    name: 'admin-dashboard',
    component: DashboardPage,
  },
  {
    path: '/admin/basics',
    name: 'admin-basics',
    component: BasicsPage,
  },
  {
    path: '/admin/permissions',
    name: 'admin-permissions',
    component: PermissionsPage,
  },
  {
    path: '/admin/appearance',
    name: 'admin-appearance',
    component: AppearancePage,
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: UsersPage,
  },
  {
    path: '/admin/flags',
    name: 'admin-flags',
    component: FlagsPage,
  },
  {
    path: '/admin/tags',
    name: 'admin-tags',
    component: TagsPage,
  },
  {
    path: '/admin/mail',
    name: 'admin-mail',
    component: MailPage,
  },
  {
    path: '/admin/advanced',
    name: 'admin-advanced',
    component: AdvancedPage,
  },
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
