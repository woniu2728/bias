export function useDiscussionListPageActions({
  discussionListContextData,
  route,
  startDiscussion,
}) {
  function handleStartDiscussion() {
    return startDiscussion({
      extensionState: buildStartDiscussionExtensionState(),
      source: route.name?.toString() || 'index',
    })
  }

  function buildStartDiscussionExtensionState() {
    const contextData = discussionListContextData?.value || {}
    return Object.values(contextData).reduce((state, item) => {
      const extensionState = item?.startDiscussionExtensionState
      if (!extensionState || typeof extensionState !== 'object') {
        return state
      }
      return mergeExtensionState(state, extensionState)
    }, {})
  }

  return {
    handleStartDiscussion,
  }
}

function mergeExtensionState(base, next) {
  const merged = { ...base }
  for (const [key, value] of Object.entries(next)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      merged[key] = {
        ...(merged[key] && typeof merged[key] === 'object' ? merged[key] : {}),
        ...value,
      }
    } else {
      merged[key] = value
    }
  }
  return merged
}
