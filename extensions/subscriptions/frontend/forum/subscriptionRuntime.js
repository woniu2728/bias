export function isDiscussionSubscribed(discussion) {
  return Boolean(discussion?.is_subscribed)
}

export function getSubscriptionActionLabel(discussion, { pending = false } = {}) {
  if (pending) return '提交中...'
  return isDiscussionSubscribed(discussion) ? '取消关注' : '关注讨论'
}

export function getSubscriptionActionDescription(discussion) {
  return isDiscussionSubscribed(discussion)
    ? '停止接收这条讨论后续回复通知。'
    : '接收这条讨论后续回复通知。'
}

export function shouldFollowAfterReply(user) {
  return Boolean(user?.preferences?.follow_after_reply)
}
