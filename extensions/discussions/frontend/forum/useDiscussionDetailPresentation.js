
import { computed } from '@bias/core'
import { getDiscussionPresentationItems } from '@bias/discussions'
import {
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
} from '@bias/users'
import { buildDiscussionHeroColorStyle } from './discussionHeroStyle.js'

export function useDiscussionDetailPresentation(discussion) {
  const discussionHeaderStyle = computed(() => {
    return mergeDiscussionHeroStyle(getDiscussionPresentationItems({
      discussion: discussion.value,
      surface: 'discussion-hero',
    }))
  })

  return {
    discussionHeaderStyle,
    getUserPrimaryGroupIcon,
    getUserPrimaryGroupColor(user) {
      return getUserPrimaryGroupColor(user, 'var(--forum-primary-color)')
    },
    getUserPrimaryGroupLabel
  }
}

function mergeDiscussionHeroStyle(items = []) {
  return items.reduce((style, item) => ({
    ...style,
    ...(item?.heroStyle || {}),
  }), buildDiscussionHeroColorStyle('#f2554b'))
}
