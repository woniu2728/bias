export function getUserPointsBalance(user) {
  return Number(user?.points_balance || 0)
}

export function formatPointsBalance(user) {
  return getUserPointsBalance(user)
}

export function formatPointsLabel(user, { unit = '积分' } = {}) {
  return `${getUserPointsBalance(user)} ${unit}`.trim()
}

export function buildUserPointsPath(user) {
  if (!user?.id && !user?.username) {
    return '/profile?tab=points'
  }
  const identifier = encodeURIComponent(String(user.username || user.id))
  return `/u/${identifier}?tab=points`
}

export function normalizePointsLedgerEntry(entry) {
  const item = entry && typeof entry === 'object' ? entry : {}
  return {
    id: item.id,
    delta: Number(item.delta || 0),
    balance_after: Number(item.balance_after || 0),
    kind: String(item.kind || ''),
    reason: String(item.reason || ''),
    source_type: String(item.source_type || ''),
    source_id: String(item.source_id || ''),
    idempotency_key: String(item.idempotency_key || ''),
    meta: item.meta && typeof item.meta === 'object' ? item.meta : {},
    created_at: item.created_at || '',
  }
}
