import { computed, getTrackedDiscussionIdsFromDiscussionItems, ref } from '@bias/forum'
import { flattenTags, normalizeTag, unwrapTagList } from './tagUtils.js'

export function createTagsResourceState({
  resourceStore,
}) {
  const tagIds = ref([])

  const tags = computed(() => resourceStore.list('tags', tagIds.value))
  const trackedDiscussionIds = computed(() => {
    return getTrackedDiscussionIdsFromDiscussionItems(
      tags.value
        .map(tag => tag?.last_posted_discussion)
        .filter(Boolean)
    )
  })
  const cloudTags = computed(() => flattenTags(tags.value.filter(tag => tag.children.length === 0)).slice(0, 12))

  function applyTagsResponse(response) {
    tagIds.value = resourceStore.upsertMany('tags', unwrapTagList(response).map(normalizeTag))
      .map(item => item.id)
  }

  function resetTags() {
    tagIds.value = []
  }

  return {
    applyTagsResponse,
    cloudTags,
    resetTags,
    tagIds,
    tags,
    trackedDiscussionIds,
  }
}

export function useTagsResourceState({
  resourceStore,
}) {
  return createTagsResourceState({
    resourceStore,
  })
}
