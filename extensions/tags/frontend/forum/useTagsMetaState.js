import { computed, getEmptyState, getStateBlock, getUiCopy, watch } from '@bias/forum'
import { resolveTagsMetaPayload } from './tagsMeta.js'

export function createTagsMetaState({
  forumStore,
  getEmptyStateBlock = getEmptyState,
  getStateText = getStateBlock,
  getText = getUiCopy,
  loading,
  tags,
  resolveMetaPayload = resolveTagsMetaPayload,
}) {
  const heroTitleText = computed(() => getText({
    surface: 'tags-page-hero-title',
  })?.text || '全部标签')

  const heroDescriptionText = computed(() => getText({
    surface: 'tags-page-hero-description',
    tagCount: tags.value.length,
  })?.text || (tags.value.length
    ? `浏览 ${tags.value.length} 个论坛标签，按主题发现相关讨论。`
    : '浏览论坛标签，按主题发现相关讨论。'))

  const emptyStateText = computed(() => {
    const emptyState = getEmptyStateBlock({
      surface: 'tags-page-empty',
      tags: tags.value,
    })

    return emptyState?.text || '暂无标签'
  })

  const loadingStateText = computed(() => {
    const stateBlock = getStateText({
      surface: 'tags-page-loading',
      loading: loading.value,
      tags: tags.value,
    })

    return stateBlock?.text || '加载中...'
  })

  watch(
    () => [heroTitleText.value, heroDescriptionText.value, tags.value.length],
    () => {
      forumStore.setPageMeta(resolveMetaPayload({
        tagCount: tags.value.length,
        titleText: heroTitleText.value,
        descriptionText: heroDescriptionText.value,
      }))
    },
    { immediate: true }
  )

  return {
    emptyStateText,
    heroDescriptionText,
    heroTitleText,
    loadingStateText,
  }
}

export function useTagsMetaState(options) {
  return createTagsMetaState(options)
}
