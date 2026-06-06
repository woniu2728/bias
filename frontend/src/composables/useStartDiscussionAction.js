export function useStartDiscussionAction({
  authStore,
  composerStore,
  router
}) {
  function startDiscussion({
    redirectToLogin = true,
    extensionState = {},
    source = 'unknown',
  } = {}) {
    if (!authStore.isAuthenticated) {
      if (redirectToLogin) {
        router.push('/login')
      }
      return false
    }

    if (!authStore.canStartDiscussion) return false

    composerStore.openDiscussionComposer({
      extensions: extensionState,
      source
    })
    return true
  }

  return {
    startDiscussion
  }
}
