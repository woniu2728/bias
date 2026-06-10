export function createDiscussionListLoadState({
  getErrorMessage,
  getText,
  listStateFactory,
  loadInitialResources,
  loadMoreDiscussions,
  modalStore,
  refreshDiscussions,
  resetResources,
}) {
  const listState = listStateFactory({
    async load({ mode }) {
      if (mode === 'initial') {
        await loadInitialResources()
        return null
      }

      if (mode === 'append') {
        await loadMoreDiscussions()
        return null
      }

      await refreshDiscussions()
      return null
    },
    reset: resetResources,
  })

  function uiText(surface, fallback, context = {}) {
    return getText({
      surface,
      ...context,
    })?.text || fallback
  }

  async function showDiscussionListError(actionType, error, fallback = uiText('discussion-list-action-retry-message', '请稍后重试')) {
    await modalStore.alert({
      title: uiText('discussion-list-action-failed-title', '操作失败', { actionType }),
      message: getErrorMessage(error, fallback),
      tone: 'danger'
    })
  }

  async function refreshPageData() {
    try {
      await listState.refresh({
        mode: 'initial',
        forceLoading: true,
      })
    } catch (error) {
      resetResources()
      console.error('加载首页列表失败:', error)
    }
  }

  async function refreshDiscussionList() {
    try {
      await listState.refresh({
        mode: 'refresh',
      })
    } catch (error) {
      console.error('刷新讨论列表失败:', error)
      await showDiscussionListError('refresh', error)
    }
  }

  async function loadMore() {
    try {
      await listState.refresh({
        mode: 'append',
      })
    } catch (error) {
      console.error('加载更多讨论失败:', error)
      await showDiscussionListError('load-more', error)
    }
  }

  return {
    listState,
    loadMore,
    refreshDiscussionList,
    refreshPageData,
    uiText,
  }
}
