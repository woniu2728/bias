import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getAdminAdvancedPageActionMeta,
  getAdminApprovalQueuePageConfig,
  getAdminModulesPageCopy,
  registerAdminAdvancedPageActionMeta,
  registerAdminApprovalQueueNoteTemplate,
  registerAdminApprovalQueuePageConfig,
  registerAdminModulesPageCopy,
} from './pages.js'


function uniqueKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}


test('admin page copy registry returns the first visible item by order', () => {
  const fallbackKey = uniqueKey('modules-copy-fallback')
  const preferredKey = uniqueKey('modules-copy-preferred')

  registerAdminModulesPageCopy({
    key: fallbackKey,
    order: 30,
    resolve: () => ({
      title: 'fallback',
    }),
  })

  registerAdminModulesPageCopy({
    key: preferredKey,
    order: 10,
    resolve: () => ({
      title: 'preferred',
    }),
  })

  const copy = getAdminModulesPageCopy()

  assert.equal(copy.key, preferredKey)
  assert.equal(copy.title, 'preferred')
})

test('approval queue page config merges note templates from dedicated registry', () => {
  const configKey = uniqueKey('approval-config')
  const templateKey = uniqueKey('approval-template')

  registerAdminApprovalQueuePageConfig({
    key: configKey,
    resolve: () => ({
      filters: ['pending'],
    }),
  })

  registerAdminApprovalQueueNoteTemplate({
    key: templateKey,
    order: 5,
    resolve: () => ({
      label: '通过模板',
      value: '内容符合规范。',
    }),
  })

  const config = getAdminApprovalQueuePageConfig()

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
