import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getAdminDashboardStats,
  registerAdminDashboardStat,
} from './dashboard.js'
import {
  getAdminAdvancedPageActionMeta,
  getAdminPageConfig,
  getAdminPageCopy,
  registerAdminAdvancedPageActionMeta,
  registerAdminPageConfig,
  registerAdminPageCopy,
  registerAdminPageNoteTemplate,
} from './pages.js'
import { runWithExtensionScope } from '../../common/extensionRuntime.js'
import { clearAdminRegistryExtensions } from './shared.js'


function uniqueKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}


test('admin page copy registry returns the first visible item by order', () => {
  const pageKey = uniqueKey('extension-copy-page')
  const fallbackKey = uniqueKey('extension-copy-fallback')
  const preferredKey = uniqueKey('extension-copy-preferred')

  registerAdminPageCopy(pageKey, {
    key: fallbackKey,
    order: 30,
    resolve: () => ({
      title: 'fallback',
    }),
  })

  registerAdminPageCopy(pageKey, {
    key: preferredKey,
    order: 10,
    resolve: () => ({
      title: 'preferred',
    }),
  })

  const copy = getAdminPageCopy(pageKey)

  assert.equal(copy.key, preferredKey)
  assert.equal(copy.title, 'preferred')
})

test('admin page config merges note templates by page key', () => {
  const pageKey = uniqueKey('extension-review-page')
  const configKey = uniqueKey('review-config')
  const templateKey = uniqueKey('review-template')

  registerAdminPageConfig(pageKey, {
    key: configKey,
    resolve: () => ({
      filters: ['pending'],
    }),
  })

  registerAdminPageNoteTemplate(pageKey, {
    key: templateKey,
    order: 5,
    resolve: () => ({
      label: 'Review template',
      value: 'Looks good.',
    }),
  })

  const config = getAdminPageConfig(pageKey)

  assert.equal(config.key, configKey)
  assert.deepEqual(config.filters, ['pending'])
  assert.equal(config.noteTemplates.length > 0, true)
  assert.equal(config.noteTemplates.some(item => item.key === templateKey), true)
})

test('admin page action meta registry stays available through aggregate exports', () => {
  const hiddenKey = uniqueKey('advanced-action-hidden')
  const visibleKey = uniqueKey('advanced-action-visible')

  registerAdminAdvancedPageActionMeta({
    key: hiddenKey,
    order: 5,
    isVisible: () => false,
    resolve: () => ({
      saveLabel: 'hidden',
    }),
  })

  registerAdminAdvancedPageActionMeta({
    key: visibleKey,
    order: 20,
    resolve: () => ({
      saveLabel: 'visible',
    }),
  })

  const actionMeta = getAdminAdvancedPageActionMeta()

  assert.equal(actionMeta.key, visibleKey)
  assert.equal(actionMeta.saveLabel, 'visible')
})

test('admin registry scopes extension items and filters by module state', () => {
  const statKey = uniqueKey('extension-dashboard-stat')

  runWithExtensionScope('scoped-admin', () => {
    registerAdminDashboardStat({
      key: statKey,
      moduleId: 'approval',
      resolve: () => ({
        label: 'Scoped stat',
        value: 1,
      }),
    })
  })

  const visibleStats = getAdminDashboardStats({
    isModuleEnabled: moduleId => moduleId === 'approval',
  })
  assert.equal(visibleStats.some(item => item.key === statKey && item.extensionId === 'scoped-admin'), true)

  const hiddenStats = getAdminDashboardStats({
    isModuleEnabled: moduleId => moduleId !== 'approval',
  })
  assert.equal(hiddenStats.some(item => item.key === statKey), false)

  clearAdminRegistryExtensions('scoped-admin')
  assert.equal(getAdminDashboardStats().some(item => item.key === statKey), false)
})
