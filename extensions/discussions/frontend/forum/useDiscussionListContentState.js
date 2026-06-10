
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

export function createDiscussionListContentState({
  getText = getUiCopy,
}) {
  const refreshingText = computed(() => getText({
    surface: 'discussion-list-refreshing',
  })?.text || '正在刷新讨论')

  const loadMoreText = computed(() => getText({
    surface: 'discussion-list-load-more',
  })?.text || '加载更多讨论')

  const loadingMoreText = computed(() => getText({
    surface: 'discussion-list-loading-more',
  })?.text || '正在加载讨论...')

  return {
    loadMoreText,
    loadingMoreText,
    refreshingText,
  }
}

export function useDiscussionListContentState(options = {}) {
  return createDiscussionListContentState(options)
}
