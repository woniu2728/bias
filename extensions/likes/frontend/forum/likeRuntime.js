export function canLikePost(post) {
  return Boolean(post?.can_like ?? false)
}

export function getPostLikeCount(post) {
  return Number(post?.like_count || 0)
}

export function isPostLiked(post) {
  return Boolean(post?.is_liked)
}

export function buildLikeSummary(post) {
  const count = getPostLikeCount(post)
  if (count <= 0) {
    return ''
  }
  if (isPostLiked(post)) {
    return count === 1 ? '你赞了这条回复' : `你和其他 ${count - 1} 人赞了这条回复`
  }
  return `${count} 人赞了这条回复`
}
