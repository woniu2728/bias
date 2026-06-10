
import {
  api,
  ref,
  computed,
  useResourceStore
} from '@bias/core'

import { normalizeDiscussion } from '@bias/discussions'
import { useDiscussionPostStreamState } from './useDiscussionPostStreamState'

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
