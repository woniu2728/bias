
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

function createDefaultSortOptions(getText) {
  return [
    {
      code: 'latest',
      label: getText({
        surface: 'discussion-list-toolbar-sort-label',
        code: 'latest',
      })?.text || '最新活跃',
      icon: 'fas fa-clock',
    },
    {
      code: 'newest',
      label: getText({
        surface: 'discussion-list-toolbar-sort-label',
        code: 'newest',
      })?.text || '新主题',
      icon: 'fas fa-file-alt',
    },
    {
      code: 'top',
      label: getText({
        surface: 'discussion-list-toolbar-sort-label',
        code: 'top',
      })?.text || '热门',
      icon: 'fas fa-fire',
    },
  ]
}

export function createDiscussionListToolbarState({
  getText = getUiCopy,
  markingAllRead,
  refreshing,
  sortOptions,
}) {
  const normalizedSortOptions = computed(() => {
    if (sortOptions.value.length) {
      return sortOptions.value.filter(option => option.toolbar_visible !== false)
    }

    return createDefaultSortOptions(getText)
  })

  const markAllReadTitleText = computed(() => getText({
    surface: 'discussion-list-toolbar-mark-read',
    markingAllRead: markingAllRead.value,
  })?.text || '全部标记为已读')

  const refreshTitleText = computed(() => getText({
    surface: 'discussion-list-toolbar-refresh',
    refreshing: refreshing.value,
  })?.text || '刷新')

  return {
    markAllReadTitleText,
    normalizedSortOptions,
    refreshTitleText,
  }
}

export function useDiscussionListToolbarState(options) {
  return createDiscussionListToolbarState(options)
}
