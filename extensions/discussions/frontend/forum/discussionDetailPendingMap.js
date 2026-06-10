export function hasPendingPostAction(pendingIds, postId) {
  return pendingIds.includes(postId)
}

export function addPendingPostAction(pendingIds, postId) {
  if (pendingIds.includes(postId)) {
    return pendingIds
  }
  return [...pendingIds, postId]
}

export function removePendingPostAction(pendingIds, postId) {
  return pendingIds.filter(id => id !== postId)
}
