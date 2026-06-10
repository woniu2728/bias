
import {
  computed } from '@bias/core'
import { getDiscussionPresentationItems,
  getDiscussionStateBadges } from '@bias/discussions'
import { getFeedbackNote,
  getUiCopy
} from '@bias/forum'

export function createDiscussionListItemMetaState({
  discussion,
  formatRelativeTime,
  getDiscussionFeedbackNote = getFeedbackNote,
  getDiscussionBadges = getDiscussionStateBadges,
  getDiscussionPresentation = getDiscussionPresentationItems,
  getText = getUiCopy,
}) {
  const discussionStateBadges = computed(() => getDiscussionBadges({
    discussion: discussion.value,
    surface: 'discussion-list-item',
  }))

  const feedbackNote = computed(() => getDiscussionFeedbackNote({
    discussion: discussion.value,
    surface: 'discussion-list-item',
  }))

  const presentationItems = computed(() => getDiscussionPresentation({
    discussion: discussion.value,
    surface: 'discussion-list-item-meta',
  }))

  const createdAtText = computed(() => {
    const relativeTime = formatRelativeTime(discussion.value.created_at)

    return getText({
      surface: 'discussion-list-item-created-at',
      createdAt: discussion.value.created_at,
      relativeTime,
    })?.text || `发起于 ${relativeTime}`
  })

  const lastPostedAtText = computed(() => {
    const relativeTime = formatRelativeTime(discussion.value.last_posted_at)

    return getText({
      surface: 'discussion-list-item-last-posted-at',
      lastPostedAt: discussion.value.last_posted_at,
      relativeTime,
    })?.text || `最后回复 ${relativeTime}`
  })

  return {
    createdAtText,
    discussionStateBadges,
    feedbackNote,
    lastPostedAtText,
    presentationItems,
  }
}

export function useDiscussionListItemMetaState(options) {
  return createDiscussionListItemMetaState(options)
}
