import { computed, ref } from 'vue'
import api from '@/api'
import { useResourceStore } from '@/stores/resource'
import { normalizeDiscussion } from '@/utils/forum'
import { useDiscussionPostStreamState } from '@/composables/useDiscussionPostStreamState'

export function useDiscussionDetailState({
  authStore,
  forumStore,
  route,
  router,
}) {
  const resourceStore = useResourceStore()
  const discussionId = ref(null)
  const discussion = computed(() => (discussionId.value ? resourceStore.get('discussions', discussionId.value) : null))

  async function loadDiscussion() {
    const data = await api.get(`/discussions/${route.params.id}`)
    const normalizedDiscussion = resourceStore.upsert('discussions', normalizeDiscussion(data))
    discussionId.value = normalizedDiscussion.id
    return normalizedDiscussion
  }

  function patchDiscussion(patch) {
    if (!discussionId.value) return null
    return resourceStore.patch('discussions', discussionId.value, patch)
  }

  const postStream = useDiscussionPostStreamState({
    authStore,
    discussion,
    discussionId,
    forumStore,
    route,
    router,
    patchDiscussion,
    async refreshDiscussion() {
      await refreshDiscussion()
    },
  })

  async function refreshDiscussion(options = {}) {
    await loadDiscussion()
    await postStream.refreshPostStream({
      keepLoading: Boolean(options.keepLoading),
    })
  }

  return {
    discussion,
    discussionId,
    patchDiscussion,
    postStream,
    refreshDiscussion,
  }
}
