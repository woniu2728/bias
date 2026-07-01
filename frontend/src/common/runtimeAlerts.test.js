import assert from 'node:assert/strict'
import test from 'node:test'

import {
  normalizeRuntimeAlert,
  removeRuntimeAlert,
  upsertRuntimeAlert,
} from './runtimeAlerts.js'

test('extension frontend runtime errors become user-facing degradation alerts', () => {
  const alert = normalizeRuntimeAlert({
    extensionId: 'broken',
    operation: 'forum-entry',
    message: 'missing chunk',
  }, 'extension-runtime')

  assert.equal(alert.tone, 'warning')
  assert.equal(alert.title, '扩展前端加载失败')
  assert.equal(alert.extensionId, 'broken')
  assert.match(alert.message, /页面其他功能可继续使用/)
  assert.equal(alert.detail, 'missing chunk')
})

test('runtime alerts dedupe and keep newest alerts bounded', () => {
  const alerts = []
  const alert = normalizeRuntimeAlert({ extensionId: 'broken', operation: 'forum-entry', message: 'missing chunk' }, 'extension-runtime')

  upsertRuntimeAlert(alerts, alert)
  upsertRuntimeAlert(alerts, alert)
  assert.equal(alerts.length, 1)

  for (let index = 0; index < 8; index += 1) {
    upsertRuntimeAlert(alerts, {
      key: `alert-${index}`,
      tone: 'info',
      message: `message ${index}`,
    })
  }

  assert.equal(alerts.length, 5)
  assert.equal(alerts[0].key, 'alert-7')
  removeRuntimeAlert(alerts, 'alert-7')
  assert.equal(alerts[0].key, 'alert-6')
})
