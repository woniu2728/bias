export function getDiscussionListTrackingDiff(nextIds = [], previousIds = []) {
  const nextSet = new Set(
    nextIds
      .map(value => Number(value))
      .filter(value => Number.isInteger(value) && value > 0)
  )
  const previousSet = new Set(
    previousIds
      .map(value => Number(value))
      .filter(value => Number.isInteger(value) && value > 0)
  )

  return {
    trackIds: [...nextSet].filter(id => !previousSet.has(id)),
    untrackIds: [...previousSet].filter(id => !nextSet.has(id)),
  }
}

export function resolveDiscussionReadStatePatch(discussion, detail = {}) {
  if (!discussion) return null

  const lastReadPostNumber = Math.max(
    Number(discussion.last_read_post_number || 0),
    Number(detail.lastReadPostNumber || 0)
  )
  const unreadCount = Math.max(Number(detail.unreadCount || 0), 0)

  return {
    ...discussion,
    last_read_post_number: lastReadPostNumber,
    last_read_at: detail.lastReadAt || discussion.last_read_at,
    unread_count: unreadCount,
    is_unread: unreadCount > 0,
  }
}

export function resolveDiscussionMarkAllReadPatch(discussion, markedAllAsReadAt) {
  if (!discussion) return null

  return {
    ...discussion,
    is_unread: false,
    unread_count: 0,
    last_read_post_number: discussion.last_post_number || discussion.last_read_post_number || 0,
    last_read_at: markedAllAsReadAt || discussion.last_read_at,
  }
}
