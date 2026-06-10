import { onBeforeUnmount, onMounted, watch } from '@bias/core'

export function createProfilePageLifecycle({
  addForumEventListener,
  cleanupTrackedDiscussions,
  refreshProfile,
  removeForumEventListener,
  resetProfileScope,
}) {
  async function handleMounted() {
    await refreshProfile()
    addForumEventListener()
  }

  function handleBeforeUnmount() {
    removeForumEventListener()
    cleanupTrackedDiscussions()
  }

  async function handleRouteProfileChange() {
    resetProfileScope()
    await refreshProfile()
  }

  return {
    handleBeforeUnmount,
    handleMounted,
    handleRouteProfileChange,
  }
}

export function useProfilePageLifecycle({
  addForumEventListener,
  cleanupTrackedDiscussions,
  refreshProfile,
  removeForumEventListener,
  resetProfileScope,
  route,
}) {
  const lifecycle = createProfilePageLifecycle({
    addForumEventListener,
    cleanupTrackedDiscussions,
    refreshProfile,
    removeForumEventListener,
    resetProfileScope,
  })

  onMounted(lifecycle.handleMounted)
  onBeforeUnmount(lifecycle.handleBeforeUnmount)
  watch(() => route.params.id, lifecycle.handleRouteProfileChange)

  return lifecycle
}
