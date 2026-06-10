
import { computed } from '@bias/core'
import { getDiscussionListHero } from '@bias/discussions'
import {
  resolveDiscussionListActiveFilterCode,
} from './discussionList.js'

export function createDiscussionListHeroState({
  contextSubject,
  discussionListContexts,
  getActiveFilterCode = resolveDiscussionListActiveFilterCode,
  getHero = getDiscussionListHero,
  isFollowingPage,
  listFilter,
}) {
  const activeFilterCode = computed(() => getActiveFilterCode({
    isFollowingPage: isFollowingPage.value,
    listFilter: listFilter.value,
  }))

  const hero = computed(() => getHero({
    activeFilterCode: activeFilterCode.value,
    contexts: discussionListContexts?.value || [],
    contextSubject: contextSubject.value,
    isFollowingPage: isFollowingPage.value,
    listFilter: listFilter.value,
    surface: 'discussion-list-hero',
  }))

  return {
    activeFilterCode,
    hero,
  }
}

export function useDiscussionListHeroState(options) {
  return createDiscussionListHeroState(options)
}
