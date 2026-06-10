import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getAdminDashboardActionMeta,
  getAdminDashboardConfig,
  getAdminDashboardCopy,
  getAdminDashboardStats,
  registerAdminDashboardActionMeta,
  registerAdminDashboardConfig,
  registerAdminDashboardCopy,
  registerAdminDashboardStat,
} from './dashboard.js'
import {
  getAdminAdvancedPageActionMeta,
  getAdminPageAction,
  getAdminPageConfig,
  getAdminPageCopy,
  registerAdminAdvancedPageActionMeta,
  registerAdminPageAction,
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

test('admin page copy and config merge extension contributions by order', () => {
  const pageKey = uniqueKey('merged-page')
  const coreCopyKey = uniqueKey('merged-core-copy')
  const extensionCopyKey = uniqueKey('merged-extension-copy')
  const coreConfigKey = uniqueKey('merged-core-config')
  const extensionConfigKey = uniqueKey('merged-extension-config')

  registerAdminPageCopy(pageKey, {
    key: coreCopyKey,
    order: 10,
    resolve: () => ({
      title: 'core title',
      shared: 'core wins',
    }),
  })

  registerAdminPageCopy(pageKey, {
    key: extensionCopyKey,
    order: 20,
    resolve: () => ({
      extensionLabel: 'extension label',
      shared: 'extension fallback',
    }),
  })

  registerAdminPageConfig(pageKey, {
    key: coreConfigKey,
    order: 10,
    resolve: () => ({
      defaults: {
        cache: 'file',
        shared: 'core wins',
      },
    }),
  })

  registerAdminPageConfig(pageKey, {
    key: extensionConfigKey,
    order: 20,
    resolve: () => ({
      defaults: {
        featureEnabled: true,
        shared: 'extension fallback',
      },
    }),
  })

  const copy = getAdminPageCopy(pageKey)
  const config = getAdminPageConfig(pageKey)

  assert.equal(copy.key, coreCopyKey)
  assert.equal(copy.title, 'core title')
  assert.equal(copy.extensionLabel, 'extension label')
  assert.equal(copy.shared, 'core wins')
  assert.equal(config.key, coreConfigKey)
  assert.deepEqual(config.defaults, {
    cache: 'file',
    featureEnabled: true,
    shared: 'core wins',
  })
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

test('admin page action registry resolves extension-owned actions by page key', () => {
  const pageKey = uniqueKey('action-page')
  const actionKey = uniqueKey('send-action')

  registerAdminPageAction(pageKey, {
    key: actionKey,
    moduleId: 'demo',
    resolve: ({ marker }) => ({
      run: () => `ran:${marker}`,
    }),
  })

  const visibleAction = getAdminPageAction(pageKey, actionKey, {
    marker: 'visible',
    isModuleEnabled: moduleId => moduleId === 'demo',
  })
  const hiddenAction = getAdminPageAction(pageKey, actionKey, {
    marker: 'hidden',
    isModuleEnabled: () => false,
  })

  assert.equal(visibleAction.run(), 'ran:visible')
  assert.equal(hiddenAction, null)
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

test('admin dashboard copy config and action meta merge extension contributions', () => {
  const coreCopyKey = uniqueKey('dashboard-core-copy')
  const extensionCopyKey = uniqueKey('dashboard-extension-copy')
  const coreConfigKey = uniqueKey('dashboard-core-config')
  const extensionConfigKey = uniqueKey('dashboard-extension-config')
  const coreActionMetaKey = uniqueKey('dashboard-core-action-meta')
  const extensionActionMetaKey = uniqueKey('dashboard-extension-action-meta')

  registerAdminDashboardCopy({
    key: coreCopyKey,
    order: 10,
    resolve: () => ({
      pageTitle: 'core dashboard',
      sharedLabel: 'core wins',
    }),
  })

  registerAdminDashboardCopy({
    key: extensionCopyKey,
    order: 20,
    moduleId: 'demo',
    resolve: () => ({
      extensionLabel: 'extension dashboard',
      sharedLabel: 'extension fallback',
    }),
  })

  registerAdminDashboardConfig({
    key: coreConfigKey,
    order: 10,
    resolve: () => ({
      defaultStats: {
        runtimeName: 'Python',
        shared: 'core wins',
      },
    }),
  })

  registerAdminDashboardConfig({
    key: extensionConfigKey,
    order: 20,
    moduleId: 'demo',
    resolve: () => ({
      defaultStats: {
        extensionCount: 0,
        shared: 'extension fallback',
      },
    }),
  })

  registerAdminDashboardActionMeta({
    key: coreActionMetaKey,
    order: 10,
    resolve: () => ({
      loadingErrorText: 'core loading error',
      sharedText: 'core wins',
    }),
  })

  registerAdminDashboardActionMeta({
    key: extensionActionMetaKey,
    order: 20,
    moduleId: 'demo',
    resolve: () => ({
      extensionActionText: 'extension action',
      sharedText: 'extension fallback',
    }),
  })

  const context = { isModuleEnabled: moduleId => moduleId === 'demo' }
  const copy = getAdminDashboardCopy(context)
  const config = getAdminDashboardConfig(context)
  const actionMeta = getAdminDashboardActionMeta(context)

  assert.equal(copy.key, coreCopyKey)
  assert.equal(copy.pageTitle, 'core dashboard')
  assert.equal(copy.extensionLabel, 'extension dashboard')
  assert.equal(copy.sharedLabel, 'core wins')
  assert.equal(config.key, coreConfigKey)
  assert.deepEqual(config.defaultStats, {
    runtimeName: 'Python',
    extensionCount: 0,
    shared: 'core wins',
  })
  assert.equal(actionMeta.key, coreActionMetaKey)
  assert.equal(actionMeta.loadingErrorText, 'core loading error')
  assert.equal(actionMeta.extensionActionText, 'extension action')
  assert.equal(actionMeta.sharedText, 'core wins')

  const disabledCopy = getAdminDashboardCopy({ isModuleEnabled: () => false })
  assert.equal(disabledCopy.extensionLabel, undefined)
})
