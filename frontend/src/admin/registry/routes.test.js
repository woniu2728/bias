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

  const route = findAdminRouteByPath(detailPath.replace('/:extensionId', '/sample-hello'))

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

  const route = findAdminRouteByPath(settingsPath.replace('/:extensionId', '/sample-hello'))

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

  const route = findAdminRouteByPath(permissionsPath.replace('/:extensionId', '/sample-hello'))

  assert.equal(route?.path, permissionsPath)
})

test('admin routes preserve compatibility redirects for legacy paths', () => {
  const legacyPath = uniquePath('legacy')
  const redirectTarget = '/admin/extensions/tags/settings'

  registerAdminRoute({
    path: legacyPath,
    name: `route-${legacyPath}`,
    label: '旧入口',
    moduleId: 'tags',
    redirect: redirectTarget,
  })

  const route = findAdminRouteByPath(legacyPath)

  assert.equal(route?.redirect, redirectTarget)
})

test('admin routes preserve compatibility redirects for builtin operations pages', () => {
  const usersLegacyPath = uniquePath('users')
  const approvalLegacyPath = uniquePath('approval')
  const flagsLegacyPath = uniquePath('flags')

  registerAdminRoute({
    path: usersLegacyPath,
    name: `route-${usersLegacyPath}`,
    label: '用户旧入口',
    moduleId: 'users',
    redirect: '/admin/extensions/users/operations',
  })

  registerAdminRoute({
    path: approvalLegacyPath,
    name: `route-${approvalLegacyPath}`,
    label: '审核旧入口',
    moduleId: 'approval',
    redirect: '/admin/extensions/approval/operations',
  })

  registerAdminRoute({
    path: flagsLegacyPath,
    name: `route-${flagsLegacyPath}`,
    label: '举报旧入口',
    moduleId: 'flags',
    redirect: '/admin/extensions/flags/operations',
  })

  assert.equal(findAdminRouteByPath(usersLegacyPath)?.redirect, '/admin/extensions/users/operations')
  assert.equal(findAdminRouteByPath(approvalLegacyPath)?.redirect, '/admin/extensions/approval/operations')
  assert.equal(findAdminRouteByPath(flagsLegacyPath)?.redirect, '/admin/extensions/flags/operations')
})

test('admin routes can match internal core extension carrier pages', () => {
  registerAdminRoute({
    path: '/admin/internal/core/basics',
    name: 'admin-core-basics-internal',
    label: '核心基础设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/internal/core/appearance',
    name: 'admin-core-appearance-internal',
    label: '核心外观设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/internal/core/mail',
    name: 'admin-core-mail-internal',
    label: '核心邮件设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/internal/core/advanced',
    name: 'admin-core-advanced-internal',
    label: '核心高级设置',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/internal/core/audit-logs',
    name: 'admin-core-audit-logs-internal',
    label: '核心审计日志',
    moduleId: 'core',
    showInNavigation: false,
  })

  registerAdminRoute({
    path: '/admin/internal/core/docs',
    name: 'admin-core-docs-internal',
    label: '核心开发者文档',
    moduleId: 'core',
    showInNavigation: false,
  })

  assert.equal(findAdminRouteByPath('/admin/internal/core/basics')?.name, 'admin-core-basics-internal')
  assert.equal(findAdminRouteByPath('/admin/internal/core/appearance')?.name, 'admin-core-appearance-internal')
  assert.equal(findAdminRouteByPath('/admin/internal/core/mail')?.name, 'admin-core-mail-internal')
  assert.equal(findAdminRouteByPath('/admin/internal/core/advanced')?.name, 'admin-core-advanced-internal')
  assert.equal(findAdminRouteByPath('/admin/internal/core/audit-logs')?.name, 'admin-core-audit-logs-internal')
  assert.equal(findAdminRouteByPath('/admin/internal/core/docs')?.name, 'admin-core-docs-internal')
})
