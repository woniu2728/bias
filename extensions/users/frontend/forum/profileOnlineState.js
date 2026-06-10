export function resolveProfileOnlineState({
  userId,
  lastSeenAt,
  isUserOnline = () => false,
}) {
  const normalizedUserId = Number(userId || 0)
  if (normalizedUserId > 0 && isUserOnline(normalizedUserId)) {
    return true
  }

  if (!lastSeenAt) return false

  const lastSeen = new Date(lastSeenAt)
  const now = new Date()
  return (now - lastSeen) < 5 * 60 * 1000
}
