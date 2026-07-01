export const MAX_RUNTIME_ALERTS = 5

export function normalizeRuntimeAlert(detail = {}, source = 'application') {
  const normalizedSource = String(source || 'application').trim()
  const extensionId = String(detail.extensionId || detail.extension_id || '').trim()
  const operation = String(detail.operation || '').trim()
  const rawMessage = String(detail.message || detail.error?.message || detail.error || '').trim()

  if (normalizedSource === 'extension-runtime') {
    const title = isFrontendEntryOperation(operation) ? '扩展前端加载失败' : '扩展运行失败'
    return {
      key: buildAlertKey(normalizedSource, extensionId, operation, rawMessage),
      tone: 'warning',
      title,
      message: extensionId
        ? `扩展 ${extensionId} 当前无法加载，相关功能已临时跳过，页面其他功能可继续使用。`
        : '某个扩展当前无法加载，相关功能已临时跳过，页面其他功能可继续使用。',
      detail: rawMessage,
      extensionId,
      operation,
    }
  }

  if (normalizedSource === 'application-alert') {
    const tone = normalizeTone(detail.tone || detail.type || 'info')
    return {
      key: buildAlertKey(normalizedSource, detail.title || '', tone, detail.message || ''),
      tone,
      title: String(detail.title || '').trim(),
      message: String(detail.message || '').trim(),
      detail: '',
      timeout: detail.timeout,
    }
  }

  return {
    key: buildAlertKey(normalizedSource, operation, rawMessage),
    tone: 'danger',
    title: '运行时错误',
    message: rawMessage || '页面运行时发生错误，请刷新后重试。',
    detail: '',
    operation,
  }
}

export function upsertRuntimeAlert(alerts, alert, { limit = MAX_RUNTIME_ALERTS } = {}) {
  if (!Array.isArray(alerts) || !alert?.message) {
    return alerts
  }
  const existingIndex = alerts.findIndex(item => item.key === alert.key)
  if (existingIndex >= 0) {
    alerts.splice(existingIndex, 1, {
      ...alerts[existingIndex],
      ...alert,
    })
    return alerts
  }
  alerts.unshift(alert)
  if (alerts.length > limit) {
    alerts.splice(limit)
  }
  return alerts
}

export function removeRuntimeAlert(alerts, key) {
  if (!Array.isArray(alerts)) {
    return alerts
  }
  const index = alerts.findIndex(item => item.key === key)
  if (index >= 0) {
    alerts.splice(index, 1)
  }
  return alerts
}

function isFrontendEntryOperation(operation) {
  return ['forum-entry', 'admin-entry', 'common-entry'].includes(String(operation || '').trim())
}

function normalizeTone(tone) {
  const value = String(tone || '').trim()
  if (['success', 'warning', 'danger', 'error', 'info'].includes(value)) {
    return value === 'error' ? 'danger' : value
  }
  return 'info'
}

function buildAlertKey(...parts) {
  return parts.map(part => String(part || '').trim()).join(':')
}
