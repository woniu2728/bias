export function shouldAppendRealtimePostImmediately({
  currentVisiblePostNumber = 1,
  lastLoadedPostNumber = 0,
  postIds = [],
  postId = null,
  postNumber = 0,
}) {
  if (postId && postIds.some(id => String(id) === String(postId))) {
    return true
  }

  const normalizedLastLoaded = Number(lastLoadedPostNumber || 0)
  const normalizedCurrentVisible = Number(currentVisiblePostNumber || 1)
  const normalizedPostNumber = Number(postNumber || 0)

  if (normalizedPostNumber > 0 && normalizedPostNumber <= normalizedLastLoaded) {
    return true
  }

  return normalizedLastLoaded > 0 && (normalizedLastLoaded - normalizedCurrentVisible) <= 1
}
