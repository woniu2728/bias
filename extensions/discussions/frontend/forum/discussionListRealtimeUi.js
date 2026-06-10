import { shouldMarkForumEventAsNewReply } from '@bias/realtime'

export function resolveDiscussionNewReplyPatch(discussion, event = {}) {
  if (!discussion) return null

  const eventType = String(event.event_type || '')
  if (!shouldMarkForumEventAsNewReply(eventType, { event })) {
    return null
  }

  const payloadPostNumber = Number(event.payload?.post?.number || 0)
  const nextLastPostNumber = Math.max(
    Number(discussion.last_post_number || 0),
    payloadPostNumber,
  )
  const lastReadPostNumber = Number(discussion.last_read_post_number || 0)
  const newReplyCount = Math.max(nextLastPostNumber - lastReadPostNumber, 0)

  return {
    ...discussion,
    last_post_number: nextLastPostNumber,
    comment_count: Math.max(Number(discussion.comment_count || 0), nextLastPostNumber),
    last_posted_at: event.payload?.post?.created_at || discussion.last_posted_at,
    has_new_replies: newReplyCount > 0,
    new_reply_count: newReplyCount,
  }
}
