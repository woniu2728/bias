
import {
  watch,
  computed } from '@bias/core'
import { getUiCopy
} from '@bias/forum'
import {
  resolveDiscussionListActiveFilterCode,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from './discussionList.js'

export function createDiscussionListMetaState({
  contextSubject,
  forumStore,
  isFollowingPage,
  listFilter,
  getText = getUiCopy,
  resolveActiveFilterCode = resolveDiscussionListActiveFilterCode,
  resolveMetaDescription = resolveDiscussionListPageMetaDescription,
  resolveMetaTitle = resolveDiscussionListPageMetaTitle,
  route,
  searchQuery,
}) {
  const activeFilterCode = computed(() => resolveActiveFilterCode({
    isFollowingPage: isFollowingPage.value,
    listFilter: listFilter.value,
  }))

  const subjectName = computed(() => contextSubject.value?.name || contextSubject.value?.title || '')
  const subjectDescription = computed(() => contextSubject.value?.description || '')

  const pageMetaTitle = computed(() => getText({
    surface: 'discussion-list-page-meta-title',
    listFilter: activeFilterCode.value,
    subjectName: subjectName.value,
    searchQuery: searchQuery.value,
    hasSearchQuery: Boolean(searchQuery.value),
  })?.text || resolveMetaTitle({
    filterCode: activeFilterCode.value,
    subjectName: subjectName.value,
    searchQuery: searchQuery.value,
  }))

  const pageMetaDescription = computed(() => getText({
    surface: 'discussion-list-page-meta-description',
    listFilter: activeFilterCode.value,
    subjectName: subjectName.value,
    subjectDescription: subjectDescription.value,
    searchQuery: searchQuery.value,
    hasSearchQuery: Boolean(searchQuery.value),
  })?.text || resolveMetaDescription({
    filterCode: activeFilterCode.value,
    subjectName: subjectName.value,
    subjectDescription: subjectDescription.value,
    searchQuery: searchQuery.value,
  }))

  watch(
    () => [pageMetaTitle.value, pageMetaDescription.value, route.fullPath],
    () => {
      forumStore.setPageMeta({
        title: pageMetaTitle.value,
        description: pageMetaDescription.value,
        canonicalUrl: route.fullPath,
      })
    },
    { immediate: true }
  )

  return {
    activeFilterCode,
    pageMetaDescription,
    pageMetaTitle,
  }
}

export function useDiscussionListMetaState(options) {
  return createDiscussionListMetaState(options)
}
