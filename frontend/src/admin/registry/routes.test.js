import test from 'node:test'
import assert from 'node:assert/strict'

import {
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
