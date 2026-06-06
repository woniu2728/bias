export function resolveNotificationMetaPayload({
  activeLabel,
  activeType,
  currentPage,
  unreadOnly,
  viewMode,
}) {
  const normalizedLabel = String(activeLabel || '').trim() || '通知'
  const query = new URLSearchParams()

  if (typeof activeType === 'string' && activeType.trim()) {
    query.set('type', activeType.trim())
  }
  if (Number(currentPage) > 1) {
    query.set('page', String(Number(currentPage)))
  }
  if (unreadOnly) {
    query.set('state', 'unread')
  }
  if (String(viewMode || '').trim() === 'grouped') {
    query.set('view', 'grouped')
  }

  const title = unreadOnly ? `${normalizedLabel}未读通知` : `${normalizedLabel}`
  const description = unreadOnly
    ? '查看论坛中的未读回复提醒、提及、点赞、审核和系统通知。'
    : '查看论坛中的回复提醒、提及、点赞、审核和系统通知。'

  return {
    title,
    description,
    canonicalUrl: `/notifications${query.size ? `?${query.toString()}` : ''}`,
  }
}
