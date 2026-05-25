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
