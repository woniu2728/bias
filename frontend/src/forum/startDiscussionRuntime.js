import { getStartDiscussionProvider } from './frontendRegistry.js'

export function useStartDiscussionAction({
  authStore = null,
  composerStore = null,
  router = null,
} = {}) {
  function startDiscussion(options = {}) {
    const context = {
      authStore,
      composerStore,
      router,
      redirectToLogin: true,
      extensionState: {},
      source: 'unknown',
      ...options,
    }
    const provider = getStartDiscussionProvider(context)
    const handler = provider?.start || provider?.open || provider?.handle

    if (typeof handler !== 'function') {
      return false
    }

    return handler(context)
  }

  return {
    startDiscussion,
  }
}
