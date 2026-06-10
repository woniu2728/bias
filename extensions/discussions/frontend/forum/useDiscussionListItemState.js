
import { computed } from '@bias/core'
import { getDiscussionBadges } from '@bias/discussions'

export function createDiscussionListItemState({
  discussion,
  getBadges = getDiscussionBadges,
}) {
  const discussionBadges = computed(() => getBadges({
    discussion: discussion.value,
    surface: 'discussion-list-item',
  }))
  const hasNewReplies = computed(() => Boolean(discussion.value?.has_new_replies))
  const newReplyCount = computed(() => Math.max(Number(discussion.value?.new_reply_count || 0), 0))

  return {
    discussionBadges,
    hasNewReplies,
    newReplyCount,
  }
}

export function useDiscussionListItemState(options) {
  return createDiscussionListItemState(options)
}
