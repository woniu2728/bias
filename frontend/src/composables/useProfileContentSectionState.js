import { computed } from 'vue'
import {
  getFeedbackNote,
  getDiscussionStateBadges,
  getEmptyState,
  getPostStateBadges,
  getStateBlock,
} from '../forum/frontendRegistry.js'

export function createProfileContentSectionState({
  getFeedback = getFeedbackNote,
  getDiscussionBadges = getDiscussionStateBadges,
  getEmpty = getEmptyState,
  getPostBadges = getPostStateBadges,
  getState = getStateBlock,
  isOwnProfile,
  items,
  kind,
  loading,
}) {
  const isDiscussionKind = kind === 'discussion'
  const loadingSurface = isDiscussionKind ? 'profile-discussion-loading' : 'profile-post-loading'
  const emptySurface = isDiscussionKind ? 'profile-discussion-empty' : 'profile-post-empty'
  const badgeSurface = isDiscussionKind ? 'profile-discussion' : 'profile-post'
  const defaultEmptyText = isDiscussionKind ? '暂无讨论' : '暂无回复'

  const loadingStateText = computed(() => {
    const context = {
      surface: loadingSurface,
      loading: loading.value,
      isOwnProfile: isOwnProfile.value,
    }

    if (isDiscussionKind) {
      context.discussions = items.value
    } else {
      context.posts = items.value
    }

    return getState(context)?.text || '加载中...'
  })

  const emptyStateText = computed(() => {
    const context = {
      surface: emptySurface,
      isOwnProfile: isOwnProfile.value,
    }

    if (isDiscussionKind) {
      context.discussions = items.value
    } else {
      context.posts = items.value
    }

    return getEmpty(context)?.text || defaultEmptyText
  })

  function getStateBadges(item) {
    return isDiscussionKind
      ? getDiscussionBadges({
          discussion: item,
          surface: badgeSurface,
        })
      : getPostBadges({
          post: item,
          surface: badgeSurface,
        })
  }

  function getFeedbackNoteText(item) {
    return isDiscussionKind
      ? (getFeedback({
          discussion: item,
          surface: badgeSurface,
        })?.text || '')
      : (getFeedback({
          post: item,
          surface: badgeSurface,
        })?.text || '')
  }

  return {
    emptyStateText,
    getFeedbackNoteText,
    getStateBadges,
    loadingStateText,
  }
}

export function useProfileContentSectionState(options) {
  return createProfileContentSectionState(options)
}
