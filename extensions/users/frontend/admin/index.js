import { extendAdmin } from '@bias/admin'
import { ExtensionGeneratedPermissionsPage } from '@bias/admin/components'
import UsersPage from './UsersPage.vue'
import { buildUsersPageExtender } from './usersPageBootstrap.js'

export const extend = [
  extendAdmin(admin => admin.route({
    path: '/admin/users',
    name: 'admin-users',
    component: UsersPage,
    icon: 'fas fa-users',
    label: '用户管理',
    navDescription: '管理论坛用户账号、状态和用户组。',
    navSection: 'core',
    navOrder: 80,
    showInDashboardActions: true,
    dashboardActionLabel: '管理用户',
    moduleId: 'users',
  })),

  buildUsersPageExtender(),
]

export function resolvePermissionsPage() {
  return ExtensionGeneratedPermissionsPage
}
