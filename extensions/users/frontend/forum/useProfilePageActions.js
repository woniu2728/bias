export function useProfilePageActions({
  activeTab,
  markPostsRequestedForCurrentUser,
  pushRouteState,
  userId,
}) {
  function switchTab(tab) {
    const nextTab = String(tab || '').trim() || 'discussions'
    if (nextTab === activeTab.value) return false

    if (nextTab === 'posts' && userId.value) {
      markPostsRequestedForCurrentUser()
    }

    void pushRouteState({
      activeTab: nextTab,
    })

    return true
  }

  return {
    switchTab,
  }
}
