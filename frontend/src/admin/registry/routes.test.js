import test from 'node:test'
import assert from 'node:assert/strict'

import {
  findAdminRouteByPath,
  getAdminDashboardActions,
  getAdminNavSections,
  getAdminRoutes,
  registerAdminRoute,
} from './routes.js'


function uniquePath(name) {
  return `/admin/test-${name}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}


test('admin routes respect runtime module visibility filter', () => {
  const enabledPath = uniquePath('enabled')
  const disabledPath = uniquePath('disabled')

  registerAdminRoute({
    path: enabledPath,
    name: `route-${enabledPath}`,
    label: '启用路由',
    moduleId: 'enabled-module',
    navOrder: 801,
    showInDashboardActions: true,
  })

  registerAdminRoute({
    path: disabledPath,
    name: `route-${disabledPath}`,
    label: '停用路由',
    moduleId: 'disabled-module',
    navOrder: 802,
    showInDashboardActions: true,
  })

  const isModuleEnabled = (moduleId) => moduleId !== 'disabled-module'
  const routes = getAdminRoutes({ isModuleEnabled })
  const sections = getAdminNavSections({ isModuleEnabled })
  const actions = getAdminDashboardActions({ isModuleEnabled })

  assert.equal(routes.some(item => item.path === enabledPath), true)
  assert.equal(routes.some(item => item.path === disabledPath), false)
  assert.equal(sections.some(section => section.items.some(item => item.path === enabledPath)), true)
  assert.equal(sections.some(section => section.items.some(item => item.path === disabledPath)), false)
  assert.equal(actions.some(item => item.to === enabledPath), true)
  assert.equal(actions.some(item => item.to === disabledPath), false)
})

test('admin routes can match dynamic paths for route guards', () => {
  const detailPath = uniquePath('extensions') + '/:extensionId'

  registerAdminRoute({
    path: detailPath,
    name: `route-${detailPath}`,
    label: '动态详情页',
    moduleId: 'core',
    navOrder: 803,
    showInNavigation: false,
  })

  const route = findAdminRouteByPath(detailPath.replace('/:extensionId', '/alpha-tools'))

  assert.equal(route?.path, detailPath)
})

test('admin routes can match extension settings child paths', () => {
  const settingsPath = uniquePath('extensions') + '/:extensionId/settings'

  registerAdminRoute({
    path: settingsPath,
    name: `route-${settingsPath}`,
    label: '扩展设置页',
    moduleId: 'core',
    navOrder: 804,
    showInNavigation: false,
  })

  const route = findAdminRouteByPath(settingsPath.replace('/:extensionId', '/alpha-tools'))

  assert.equal(route?.path, settingsPath)
})

test('admin routes can match extension permissions child paths', () => {
  const permissionsPath = uniquePath('extensions') + '/:extensionId/permissions'

  registerAdminRoute({
    path: permissionsPath,
    name: `route-${permissionsPath}`,
    label: '扩展权限页',
    moduleId: 'core',
    navOrder: 805,
    showInNavigation: false,
  })

  const route = findAdminRouteByPath(permissionsPath.replace('/:extensionId', '/alpha-tools'))

  assert.equal(route?.path, permissionsPath)
})

test('admin dashboard actions exclude redirect-only routes', () => {
  const directPath = uniquePath('direct-action')
  const redirectPath = uniquePath('redirect-action')

  registerAdminRoute({
    path: directPath,
    name: `route-${directPath}`,
    label: '直接操作',
    moduleId: 'core',
    showInDashboardActions: true,
  })

  registerAdminRoute({
    path: redirectPath,
    name: `route-${redirectPath}`,
    label: '跳转操作',
    moduleId: 'route-demo',
    redirect: '/admin/extensions/route-demo/settings',
    showInDashboardActions: true,
  })

  const actions = getAdminDashboardActions({ isModuleEnabled: () => true })

  assert.equal(actions.some(item => item.to === directPath), true)
  assert.equal(actions.some(item => item.to === redirectPath), false)
})

test('admin routes can match first-class core admin pages directly', () => {
  registerAdminRoute({
    path: '/admin/basics',
    name: 'admin-core-basics',
    label: '基础设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/appearance',
    name: 'admin-core-appearance',
    label: '外观设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/mail',
    name: 'admin-core-mail',
    label: '邮件设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/advanced',
    name: 'admin-core-advanced',
    label: '高级设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/audit-logs',
    name: 'admin-core-audit-logs',
    label: '审计日志',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/extension-demo-a',
    name: 'admin-extension-demo-a',
    label: '扩展页面 A',
    moduleId: 'extension-demo-a',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/extension-demo-b',
    name: 'admin-extension-demo-b',
    label: '扩展页面 B',
    moduleId: 'extension-demo-b',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/extension-demo-c',
    name: 'admin-extension-demo-c',
    label: '扩展页面 C',
    moduleId: 'extension-demo-c',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/docs',
    name: 'admin-core-docs',
    label: '开发者文档',
    moduleId: 'core',
    showInNavigation: false,
  })

  assert.equal(findAdminRouteByPath('/admin/basics')?.name, 'admin-core-basics')
  assert.equal(findAdminRouteByPath('/admin/appearance')?.name, 'admin-core-appearance')
  assert.equal(findAdminRouteByPath('/admin/mail')?.name, 'admin-core-mail')
  assert.equal(findAdminRouteByPath('/admin/advanced')?.name, 'admin-core-advanced')
  assert.equal(findAdminRouteByPath('/admin/audit-logs')?.name, 'admin-core-audit-logs')
  assert.equal(findAdminRouteByPath('/admin/extension-demo-a')?.name, 'admin-extension-demo-a')
  assert.equal(findAdminRouteByPath('/admin/extension-demo-b')?.name, 'admin-extension-demo-b')
  assert.equal(findAdminRouteByPath('/admin/extension-demo-c')?.name, 'admin-extension-demo-c')
  assert.equal(findAdminRouteByPath('/admin/docs')?.name, 'admin-core-docs')
})

test('admin navigation keeps extension section visible when extension-owned routes exist', () => {
  registerAdminRoute({
    path: '/admin/extensions/alpha-tools',
    name: 'admin-extension-alpha-tools',
    label: 'Alpha Tools',
    moduleId: 'alpha-tools',
    extensionId: 'alpha-tools',
    navSection: 'feature',
    navOrder: 900,
    showInNavigation: true,
  })

  registerAdminRoute({
    path: '/admin/extensions/alpha-tools/settings',
    name: 'admin-extension-alpha-tools-settings',
    label: 'Alpha Tools Settings',
    moduleId: 'alpha-tools',
    extensionId: 'alpha-tools',
    showInNavigation: false,
  })

  const sections = getAdminNavSections({ isModuleEnabled: () => true })
  const extensionSection = sections.find(section => section.key === 'extensions')

  assert.equal(Boolean(extensionSection), true)
  assert.equal(extensionSection.items.some(item => item.path === '/admin/extensions/alpha-tools'), true)
})

test('admin navigation keeps extension-owned first-class admin pages in core sections', () => {
  registerAdminRoute({
    path: '/admin/users-test',
    name: 'admin-users-test',
    label: '用户管理',
    moduleId: 'users',
    extensionId: 'users',
    navSection: 'core',
    navOrder: 80,
    showInNavigation: true,
  })

  const sections = getAdminNavSections({ isModuleEnabled: () => true })
  const coreSection = sections.find(section => section.key === 'core')

  assert.equal(Boolean(coreSection), true)
  assert.equal(coreSection.items.some(item => item.path === '/admin/users-test'), true)
})
