
import {
  computed } from '@bias/core'
import { getDiscussionPresentationItems,
  getDiscussionReviewBanner } from '@bias/discussions'
import { getHeroMetaItems
} from '@bias/forum'

export function createDiscussionHeroState({
  authStore,
  canEditDiscussion,
  discussion,
  getHeroMeta = getHeroMetaItems,
  getPresentationItems = getDiscussionPresentationItems,
  getReviewBanner = getDiscussionReviewBanner,
}) {
  const discussionReviewBanner = computed(() => getReviewBanner({
    authStore: authStore?.value ?? authStore,
    discussion: discussion.value,
    canEditDiscussion: canEditDiscussion.value,
    surface: 'discussion-hero',
  }))

  const heroMetaItems = computed(() => getHeroMeta({
    discussion: discussion.value,
    surface: 'discussion-hero',
  }))

  const presentationItems = computed(() => getPresentationItems({
    discussion: discussion.value,
    surface: 'discussion-hero',
  }))

  return {
    discussionReviewBanner,
    heroMetaItems,
    presentationItems,
  }
}

export function useDiscussionHeroState(options) {
  return createDiscussionHeroState(options)
}
