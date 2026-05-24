<template>
  <div ref="root" class="Modal Modal--large Modal--search fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content SearchModal-content">
      <div class="Modal-close">
        <button
          type="button"
          class="Button Button--icon Button--link"
          :aria-label="closeLabelText"
          @click="modalStore.dismiss()"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="Modal-header SearchModal-header">
        <h3>{{ titleText }}</h3>
      </div>

      <div class="Modal-body SearchModal-body">
        <div class="SearchModal-inputWrap">
          <i class="fas fa-search"></i>
          <input
            ref="inputRef"
            v-model="query"
            type="search"
            class="SearchModal-input"
            :placeholder="inputPlaceholderText"
            @keydown.down.prevent="moveSelection(1)"
            @keydown.up.prevent="moveSelection(-1)"
            @keydown.enter.prevent="submitSelection"
            @keydown.esc.prevent="modalStore.dismiss()"
          />
          <button v-if="normalizedQuery" type="button" class="SearchModal-clear" @click="clearQuery">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="SearchModal-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.value"
            type="button"
            class="SearchModal-tab"
            :class="{ active: activeType === tab.value }"
            @click="activeType = tab.value"
          >
            <span>{{ tab.label }}</span>
            <strong>{{ tab.count }}</strong>
          </button>
        </div>

        <div v-if="!normalizedQuery" class="SearchModal-state">
          <div class="SearchModal-emptyState">
            <p>{{ idleStateText }}</p>
            <div v-if="emptyPanelSections.length" class="SearchModal-commandPanel">
              <section
                v-for="section in emptyPanelSections"
                :key="section.key"
                class="SearchModal-commandSection"
              >
                <div class="SearchModal-commandHeader">{{ section.title }}</div>
                <div class="SearchModal-commandList">
                  <button
                    v-for="item in section.items"
                    :key="item.key"
                    type="button"
                    class="SearchModal-commandItem"
                    :class="{ active: activeResultIndex === item.selectIndex }"
                    :data-select-index="item.selectIndex"
                    @mouseenter="activeResultIndex = item.selectIndex"
                    @mousedown.prevent="item.action()"
                  >
                    <span class="SearchModal-commandIcon">
                      <i :class="item.icon"></i>
                    </span>
                    <span class="SearchModal-commandMain">
                      <strong>{{ item.title }}</strong>
                      <span>{{ item.subtitle }}</span>
                      <small v-if="item.description">{{ item.description }}</small>
                    </span>
                  </button>
                </div>
              </section>
            </div>
          </div>
        </div>
        <div v-else-if="loading" class="SearchModal-state">{{ loadingStateText }}</div>
        <div v-else-if="isEmpty" class="SearchModal-state">
          {{ emptyStateText }}
        </div>
        <div v-else class="SearchModal-results">
          <template v-if="activeType === 'all'">
            <section
              v-for="section in groupedSections"
              :key="section.key"
              class="SearchModal-section"
            >
              <div class="SearchModal-sectionHeader">
                <h4>{{ section.label }}</h4>
                <button type="button" class="SearchModal-sectionLink" @click="activeType = section.key">
                  {{ buildSectionLinkText(section.label) }}
                </button>
              </div>

              <div class="SearchModal-list">
                <button
                  v-for="item in section.items"
                  :key="item.key"
                  type="button"
                  class="SearchModal-result"
                  :class="{ active: activeResultIndex === item.selectIndex }"
                  :data-select-index="item.selectIndex"
                  @mouseenter="activeResultIndex = item.selectIndex"
                  @mousedown.prevent="selectItem(item)"
                >
                  <span
                    class="SearchModal-resultIcon"
                    :class="{ 'SearchModal-resultIcon--avatar': item.avatarMode }"
                    :style="getResultAvatarStyle(item)"
                  >
                    <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.titleText" />
                    <span v-else-if="item.avatarText">{{ item.avatarText }}</span>
                    <i v-else :class="item.iconClass || item.icon"></i>
                  </span>
                  <span class="SearchModal-resultMain">
                    <span class="SearchModal-resultTitle" v-html="item.titleHtml"></span>
                    <span v-if="item.subtitleHtml" class="SearchModal-resultSubtitle" v-html="item.subtitleHtml"></span>
                    <span v-if="item.metaText" class="SearchModal-resultMeta">{{ item.metaText }}</span>
                  </span>
                </button>
              </div>
            </section>
          </template>

          <div v-else class="SearchModal-list">
            <button
              v-for="item in activeItems"
              :key="item.key"
              type="button"
              class="SearchModal-result"
              :class="{ active: activeResultIndex === item.selectIndex }"
              :data-select-index="item.selectIndex"
              @mouseenter="activeResultIndex = item.selectIndex"
              @mousedown.prevent="selectItem(item)"
            >
              <span
                class="SearchModal-resultIcon"
                :class="{ 'SearchModal-resultIcon--avatar': item.avatarMode }"
                :style="getResultAvatarStyle(item)"
              >
                <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.titleText" />
                <span v-else-if="item.avatarText">{{ item.avatarText }}</span>
                <i v-else :class="item.iconClass || item.icon"></i>
              </span>
              <span class="SearchModal-resultMain">
                <span class="SearchModal-resultTitle" v-html="item.titleHtml"></span>
                <span v-if="item.subtitleHtml" class="SearchModal-resultSubtitle" v-html="item.subtitleHtml"></span>
                <span v-if="item.metaText" class="SearchModal-resultMeta">{{ item.metaText }}</span>
              </span>
            </button>
          </div>

          <div class="SearchModal-footer">
            <button
              type="button"
              class="SearchModal-fullPage"
              :class="{ active: activeResultIndex === fullPageActionIndex }"
              :data-select-index="fullPageActionIndex"
              @mouseenter="activeResultIndex = fullPageActionIndex"
              @mousedown.prevent="openFullResults"
            >
              {{ fullResultsText }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSearchFilterCatalog } from '@/composables/useSearchFilterCatalog'
import { getEmptyState, getSearchSources, getStateBlock, getUiCopy } from '@/forum/registry'
import { useForumStore } from '@/stores/forum'
import { useForumRealtimeStore } from '@/stores/forumRealtime'
import { useModalStore } from '@/stores/modal'
import { useResourceStore } from '@/stores/resource'
import api from '@/api'
import { buildTagPath } from '@/utils/forum'
import {
  unwrapList
} from '@/utils/forum'
import {
  FORUM_REALTIME_REFRESH_EVENT_TYPES,
  getTrackedDiscussionIdsFromDiscussionItems,
  getTrackedDiscussionIdsFromPostItems,
  hasTrackedDiscussionId,
} from '@/utils/forumRealtime'

const RECENT_SEARCH_STORAGE_KEY = 'bias:search:recent'
const RECENT_SEARCH_LIMIT = 6
const POPULAR_TAG_LIMIT = 6
const SEARCH_PREVIEW_LIMIT = 5

const props = defineProps({
  showing: {
    type: Boolean,
    default: false
  },
  initialQuery: {
    type: String,
    default: ''
  },
  initialType: {
    type: String,
    default: 'all'
  }
})

const router = useRouter()
const modalStore = useModalStore()
const resourceStore = useResourceStore()
const forumStore = useForumStore()
const forumRealtimeStore = useForumRealtimeStore()
const searchSources = getSearchSources({ forumStore })
const searchSourceMap = Object.fromEntries(searchSources.map(item => [item.type, item]))
const root = ref(null)
const inputRef = ref(null)
const query = ref(String(props.initialQuery || ''))
const allowedTypes = ['all', ...searchSources.map(item => item.type)]
const activeType = ref(allowedTypes.includes(props.initialType) ? props.initialType : 'all')
const searchFilterTarget = computed(() => {
  if (activeType.value === 'all') return 'all'
  return searchSourceMap[activeType.value]?.filterTarget || ''
})
const searchFilterCatalog = useSearchFilterCatalog(searchFilterTarget)
const loading = ref(false)
const discussionIds = ref([])
const postIds = ref([])
const userIds = ref([])
const popularTagIds = ref([])
const recentSearches = ref(loadRecentSearches())
const totals = ref({
  discussions: 0,
  posts: 0,
  users: 0,
})
const activeResultIndex = ref(-1)
let searchTimer = null
let requestId = 0

const normalizedQuery = computed(() => query.value.trim())
const searchResults = computed(() => ({
  discussions: resourceStore.list('discussions', discussionIds.value),
  posts: resourceStore.list('posts', postIds.value),
  users: resourceStore.list('users', userIds.value),
}))
const popularTags = computed(() => resourceStore.list('tags', popularTagIds.value))
const trackedDiscussionIds = computed(() => [
  ...getTrackedDiscussionIdsFromDiscussionItems(searchResults.value.discussions),
  ...getTrackedDiscussionIdsFromPostItems(searchResults.value.posts),
])
const tabs = computed(() => [
  { value: 'all', label: '全部', count: totals.value.discussions + totals.value.posts + totals.value.users },
  ...searchSources.map(item => ({
    value: item.type,
    label: item.label,
    count: Number(totals.value[item.type] || 0),
  })),
])
const activeTabLabel = computed(() => tabs.value.find(tab => tab.value === activeType.value)?.label || '全部')
const closeLabelText = computed(() => getUiCopy({
  surface: 'search-modal-close-label',
})?.text || '关闭搜索')
const titleText = computed(() => getUiCopy({
  surface: 'search-modal-title',
})?.text || '搜索')
const inputPlaceholderText = computed(() => getUiCopy({
  surface: 'search-modal-input-placeholder',
})?.text || '输入关键词搜索讨论、帖子和用户')
const fullResultsText = computed(() => getUiCopy({
  surface: 'search-modal-full-results',
  activeTabLabel: activeTabLabel.value,
})?.text || `查看${activeTabLabel.value}完整结果`)
const sectionLinkText = computed(() => getUiCopy({
  surface: 'search-modal-section-link',
})?.text || '只看{label}')
const modalSourceSections = computed(() => {
  const sourceItems = {
    discussions: searchResults.value.discussions,
    posts: searchResults.value.posts,
    users: searchResults.value.users,
  }

  return searchSources.map(source => {
    const sourceKey = source.type
    const items = sourceItems[sourceKey] || []
    const resultItems = typeof source.buildResultItems === 'function'
      ? source.buildResultItems(items, { query: normalizedQuery.value })
      : []

    return {
      ...source,
      key: sourceKey,
      items: resultItems,
    }
  })
})

const groupedSections = computed(() => {
  let selectIndex = 0

  return modalSourceSections.value
    .filter(section => section.items.length)
    .map(section => ({
      ...section,
      items: section.items.map(item => ({
        ...item,
        selectIndex: selectIndex++,
      }))
    }))
})

const activeItems = computed(() => {
  const activeSection = modalSourceSections.value.find(section => section.key === activeType.value)
  const items = activeSection?.items || []
  return items.map((item, index) => ({
    ...item,
    selectIndex: index,
  }))
})

const visibleSelectableItems = computed(() => {
  if (!normalizedQuery.value) {
    return emptySelectableItems.value
  }

  if (activeType.value === 'all') {
    return groupedSections.value.flatMap(section => section.items)
  }
  return activeItems.value
})

const fullPageActionIndex = computed(() => visibleSelectableItems.value.length)
const isEmpty = computed(() => modalSourceSections.value.every(section => section.items.length === 0))
const idleStateText = computed(() => {
  const emptyState = getEmptyState({
    surface: 'search-modal-idle',
    hasQuery: Boolean(normalizedQuery.value),
    searchType: activeType.value,
  })

  return emptyState?.text || '输入关键词后即可开始搜索。你可以直接回车进入完整搜索结果页。'
})
const emptyStateText = computed(() => {
  const emptyState = getEmptyState({
    surface: 'search-modal-empty',
    hasQuery: Boolean(normalizedQuery.value),
    searchType: activeType.value,
  })

  return emptyState?.text || '没有找到相关结果，试试更短的关键词或切换分类。'
})
const loadingStateText = computed(() => {
  const stateBlock = getStateBlock({
    surface: 'search-modal-loading',
    loading: loading.value,
    hasQuery: Boolean(normalizedQuery.value),
    searchType: activeType.value,
  })

  return stateBlock?.text || '搜索中...'
})
const filterSuggestions = computed(() => {
  if (!searchFilterTarget.value || activeType.value === 'all') {
    return []
  }
  return searchFilterCatalog.filterSuggestions.value
})
const recentSearchTitleText = computed(() => getUiCopy({
  surface: 'search-modal-recent-title',
})?.text || '最近搜索')
const popularTagsTitleText = computed(() => getUiCopy({
  surface: 'search-modal-popular-tags-title',
})?.text || '热门标签')
const syntaxTipsTitleText = computed(() => getUiCopy({
  surface: 'search-modal-syntax-title',
})?.text || '搜索语法')
const emptyPanelSections = computed(() => {
  if (normalizedQuery.value) {
    return []
  }

  const sections = []
  let selectIndex = 0

  if (recentSearches.value.length) {
    sections.push({
      key: 'recent-searches',
      title: recentSearchTitleText.value,
      items: recentSearches.value.map(item => ({
        key: `recent-${item.query}-${item.type || 'all'}`,
        kind: 'recent-search',
        icon: 'fas fa-history',
        title: item.query,
        subtitle: item.type && item.type !== 'all'
          ? getUiCopy({
              surface: 'search-modal-recent-subtitle',
              activeTabLabel: tabs.value.find(tab => tab.value === item.type)?.label || item.type,
            })?.text || `只看${tabs.value.find(tab => tab.value === item.type)?.label || item.type}`
          : getUiCopy({
              surface: 'search-modal-recent-all-subtitle',
            })?.text || '搜索全部内容',
        action: () => runRecentSearch(item),
        selectIndex: selectIndex++,
      })),
    })
  }

  if (popularTags.value.length) {
    sections.push({
      key: 'popular-tags',
      title: popularTagsTitleText.value,
      items: popularTags.value.map(tag => ({
        key: `tag-${tag.id}`,
        kind: 'popular-tag',
        icon: 'fas fa-tags',
        title: tag.name,
        subtitle: getUiCopy({
          surface: 'search-modal-tag-subtitle',
          count: Number(tag.discussion_count || 0),
        })?.text || `${Number(tag.discussion_count || 0)} 条讨论`,
        action: () => openTag(tag),
        selectIndex: selectIndex++,
      })),
    })
  }

  if (filterSuggestions.value.length) {
    sections.push({
      key: 'search-syntax',
      title: syntaxTipsTitleText.value,
      items: filterSuggestions.value.map(item => ({
        key: `syntax-${item.key}`,
        kind: 'syntax',
        icon: 'fas fa-terminal',
        title: item.syntax,
        subtitle: item.label,
        description: item.description || '',
        action: () => applyFilterSyntax(item.syntax),
        selectIndex: selectIndex++,
      })),
    })
  }

  return sections
})
const emptySelectableItems = computed(() => emptyPanelSections.value.flatMap(section => section.items))

watch(
  () => props.showing,
  showing => {
    if (!showing) return

    loadPopularTags()

    nextTick(() => {
      inputRef.value?.focus()
      inputRef.value?.select?.()
    })
  },
  { immediate: true }
)

watch(
  () => [normalizedQuery.value, activeType.value],
  () => {
    activeResultIndex.value = -1

    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }

    if (!normalizedQuery.value) {
      loading.value = false
      discussionIds.value = []
      postIds.value = []
      userIds.value = []
      totals.value = { discussions: 0, posts: 0, users: 0 }
      return
    }

    loading.value = true
    searchTimer = setTimeout(() => {
      fetchResults()
    }, 180)
  },
  { immediate: true }
)

watch(
  () => visibleSelectableItems.value.length,
  count => {
    if (count >= 0 && activeResultIndex.value < 0) {
      activeResultIndex.value = 0
    }

    if (activeResultIndex.value > count) {
      activeResultIndex.value = count
    }

    nextTick(() => {
      scrollActiveOptionIntoView()
    })
  }
)

watch(
  () => trackedDiscussionIds.value,
  (nextTrackedIds, previousTrackedIds = []) => {
    forumRealtimeStore.untrackDiscussionIds(previousTrackedIds)
    forumRealtimeStore.trackDiscussionIds(nextTrackedIds)
  }
)

onMounted(() => {
  loadPopularTags()
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select?.()
  })
  window.addEventListener('bias:forum-event', handleForumEvent)
})

onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  forumRealtimeStore.untrackDiscussionIds(trackedDiscussionIds.value)
  window.removeEventListener('bias:forum-event', handleForumEvent)
})

async function fetchResults() {
  const currentRequestId = ++requestId

  try {
    const data = await api.get('/search', {
      params: {
        q: normalizedQuery.value,
        type: 'all',
        limit: SEARCH_PREVIEW_LIMIT,
        preview: true,
      }
    })

    if (currentRequestId !== requestId) return

    totals.value = {
      discussions: data.discussion_total ?? unwrapList(data.discussions || []).length,
      posts: data.post_total ?? unwrapList(data.posts || []).length,
      users: data.user_total ?? unwrapList(data.users || []).length,
    }
    discussionIds.value = resourceStore.upsertMany('discussions', unwrapList(data.discussions || []))
      .map(item => item.id)
    postIds.value = resourceStore.upsertMany('posts', unwrapList(data.posts || []))
      .map(item => item.id)
    userIds.value = resourceStore.upsertMany('users', unwrapList(data.users || []))
      .map(item => item.id)
  } catch (error) {
    if (currentRequestId !== requestId) return

    console.error('加载搜索结果失败:', error)
    discussionIds.value = []
    postIds.value = []
    userIds.value = []
    totals.value = { discussions: 0, posts: 0, users: 0 }
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}

async function handleForumEvent(event) {
  const detail = event.detail || {}
  const discussionId = Number(detail.discussion_id)
  if (!hasTrackedDiscussionId(trackedDiscussionIds.value, discussionId)) {
    return
  }

  if (FORUM_REALTIME_REFRESH_EVENT_TYPES.has(detail.event_type)) {
    await fetchResults()
    return
  }

  const payload = detail.payload || {}
  resourceStore.mergePayload(payload)
}

function clearQuery() {
  query.value = ''
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function buildSectionLinkText(label) {
  return sectionLinkText.value.replace('{label}', label || '')
}

function applyFilterSyntax(syntax) {
  query.value = searchFilterCatalog.appendFilter(normalizedQuery.value, syntax)
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function moveSelection(direction) {
  const maxIndex = fullPageActionIndex.value
  if (maxIndex < 0) return

  const nextIndex = activeResultIndex.value + direction
  if (nextIndex < 0) {
    activeResultIndex.value = maxIndex
  } else if (nextIndex > maxIndex) {
    activeResultIndex.value = 0
  } else {
    activeResultIndex.value = nextIndex
  }

  nextTick(() => {
    scrollActiveOptionIntoView()
  })
}

function submitSelection() {
  if (!normalizedQuery.value) {
    const item = visibleSelectableItems.value[activeResultIndex.value]
    if (item?.action) {
      item.action()
    }
    return
  }

  if (activeResultIndex.value === fullPageActionIndex.value) {
    openFullResults()
    return
  }

  const item = visibleSelectableItems.value[activeResultIndex.value]
  if (item) {
    selectItem(item)
    return
  }

  openFullResults()
}

function selectItem(item) {
  saveRecentSearch({
    query: normalizedQuery.value,
    type: activeType.value,
  })
  modalStore.dismiss()
  router.push(item.path)
}

function openFullResults() {
  if (!normalizedQuery.value) return

  saveRecentSearch({
    query: normalizedQuery.value,
    type: activeType.value,
  })

  modalStore.dismiss()
  router.push({
    path: '/search',
    query: {
      q: normalizedQuery.value,
      ...(activeType.value === 'all' ? {} : { type: activeType.value }),
    }
  })
}

function scrollActiveOptionIntoView() {
  const currentIndex = activeResultIndex.value
  if (currentIndex < 0) return

  const activeNode = root.value?.querySelector(`[data-select-index="${currentIndex}"]`)
  activeNode?.scrollIntoView?.({ block: 'nearest' })
}

function runRecentSearch(item) {
  query.value = item.query || ''
  activeType.value = allowedTypes.includes(item.type) ? item.type : 'all'
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function openTag(tag) {
  modalStore.dismiss()
  router.push(buildTagPath(tag))
}

function getResultAvatarStyle(item) {
  if (!item?.avatarMode || item?.avatarUrl || !item?.avatarColor) {
    return null
  }

  return {
    backgroundColor: item.avatarColor,
    color: '#fff',
  }
}

function saveRecentSearch(item) {
  const queryValue = String(item?.query || '').trim()
  if (!queryValue) return

  const nextItem = {
    query: queryValue,
    type: allowedTypes.includes(item?.type) ? item.type : 'all',
  }

  const deduped = recentSearches.value.filter(existing => {
    return !(existing.query === nextItem.query && existing.type === nextItem.type)
  })

  recentSearches.value = [nextItem, ...deduped].slice(0, RECENT_SEARCH_LIMIT)
  persistRecentSearches(recentSearches.value)
}

async function loadPopularTags() {
  try {
    const response = await api.get('/tags/popular', {
      params: {
        limit: POPULAR_TAG_LIMIT,
      }
    })
    popularTagIds.value = resourceStore.upsertMany('tags', unwrapList(response))
      .map(item => item.id)
  } catch (error) {
    popularTagIds.value = []
  }
}

function loadRecentSearches() {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_SEARCH_STORAGE_KEY) || '[]')
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .map(item => ({
        query: String(item?.query || '').trim(),
        type: String(item?.type || 'all').trim() || 'all',
      }))
      .filter(item => item.query)
      .slice(0, RECENT_SEARCH_LIMIT)
  } catch (error) {
    return []
  }
}

function persistRecentSearches(items) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(RECENT_SEARCH_STORAGE_KEY, JSON.stringify(items))
}
</script>

<style scoped>
.SearchModal-content {
  min-height: min(78vh, 760px);
}

.SearchModal-header {
  padding-bottom: 16px;
  text-align: left;
}

.SearchModal-header h3 {
  margin-bottom: 8px;
}

.SearchModal-header p {
  margin: 0;
  color: #6f7f8f;
  line-height: 1.6;
}

.SearchModal-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 0;
}

.SearchModal-inputWrap {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  min-height: 52px;
  border: 1px solid #d9e3eb;
  border-radius: 14px;
  background: #fff;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.04);
}

.SearchModal-inputWrap:focus-within {
  border-color: #4d698e;
  box-shadow: 0 0 0 4px rgba(77, 105, 142, 0.12);
}

.SearchModal-inputWrap > i {
  color: #7b8794;
  font-size: 15px;
}

.SearchModal-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  font-size: 16px;
  color: #22303d;
  appearance: none;
  -webkit-appearance: none;
  border-radius: 0;
  box-shadow: none;
}

.SearchModal-input::-webkit-search-decoration,
.SearchModal-input::-webkit-search-cancel-button,
.SearchModal-input::-webkit-search-results-button,
.SearchModal-input::-webkit-search-results-decoration {
  -webkit-appearance: none;
  appearance: none;
  display: none;
}

.SearchModal-input::-ms-clear,
.SearchModal-input::-ms-reveal {
  display: none;
  width: 0;
  height: 0;
}

.SearchModal-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: #8a96a2;
  width: 24px;
  height: 24px;
  padding: 0;
  border-radius: 50%;
  transition: background 0.2s, color 0.2s;
}

.SearchModal-clear i {
  font-size: 12px;
  line-height: 1;
}

.SearchModal-clear:hover {
  background: #eef2f6;
  color: #5c6d7e;
}

.SearchModal-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.SearchModal-tab {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #d8e1e8;
  border-radius: 999px;
  background: #fff;
  color: #536476;
  font-weight: 600;
}

.SearchModal-tab strong {
  min-width: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: #eef3f7;
  color: #4d698e;
  font-size: 12px;
  line-height: 22px;
}

.SearchModal-tab.active {
  border-color: #4d698e;
  background: #edf3f9;
  color: #31465b;
}

.SearchModal-state {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #d8e1e8;
  border-radius: 14px;
  background: #fafcfd;
  color: #7a8794;
  text-align: center;
  line-height: 1.7;
  padding: 24px;
}

.SearchModal-emptyState {
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-items: center;
}

.SearchModal-emptyState p {
  margin: 0;
}

.SearchModal-syntaxPanel {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.SearchModal-commandPanel {
  width: 100%;
  display: grid;
  gap: 14px;
}

.SearchModal-commandSection {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(720px, 100%);
}

.SearchModal-commandHeader {
  color: #5d6f80;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SearchModal-commandList {
  display: grid;
  gap: 10px;
}

.SearchModal-commandItem {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #dbe4ec;
  border-radius: 12px;
  background: #fff;
  color: #31465b;
  text-align: left;
}

.SearchModal-commandItem:hover,
.SearchModal-commandItem.active {
  border-color: #4d698e;
  background: linear-gradient(180deg, #f8fbfd 0%, #edf3f9 100%);
  box-shadow: 0 10px 24px rgba(49, 70, 91, 0.08);
}

.SearchModal-commandIcon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #edf3f8;
  color: #58708a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.SearchModal-commandMain {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.SearchModal-commandMain strong {
  color: #22303d;
  font-size: 14px;
  line-height: 1.4;
}

.SearchModal-commandMain span,
.SearchModal-commandMain small {
  color: #66788a;
  line-height: 1.5;
}

.SearchModal-commandMain span {
  font-size: 13px;
}

.SearchModal-commandMain small {
  font-size: 12px;
}

.SearchModal-syntaxChip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #d8e1e8;
  border-radius: 999px;
  background: #fff;
  color: #4f6478;
  font-size: 12px;
  font-weight: 600;
}

.SearchModal-syntaxChip strong {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: #31465b;
}

.SearchModal-syntaxChip:hover {
  border-color: #4d698e;
  background: #edf3f9;
}

.SearchModal-results {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.SearchModal-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.SearchModal-sectionHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.SearchModal-sectionHeader h4 {
  margin: 0;
  color: #22303d;
  font-size: 16px;
}

.SearchModal-sectionLink {
  border: 0;
  background: transparent;
  color: #4d698e;
  font-size: 13px;
  font-weight: 700;
}

.SearchModal-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.SearchModal-result {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 15px;
  border: 1px solid #e2e8ee;
  border-radius: 12px;
  background: #fff;
  text-align: left;
  color: #34485c;
}

.SearchModal-result:hover,
.SearchModal-result.active {
  border-color: #4d698e;
  background: #f7fafd;
  box-shadow: 0 10px 24px rgba(49, 70, 91, 0.08);
}

.SearchModal-resultIcon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #eef3f7;
  color: #5f7388;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.SearchModal-resultIcon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.SearchModal-resultMain {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.SearchModal-resultTitle,
.SearchModal-resultSubtitle {
  line-height: 1.5;
}

.SearchModal-resultTitle {
  color: #22303d;
  font-size: 15px;
  font-weight: 700;
}

.SearchModal-resultSubtitle {
  color: #617282;
  font-size: 13px;
}

.SearchModal-resultMeta {
  color: #8b97a3;
  font-size: 12px;
}

.SearchModal-resultTitle :deep(mark),
.SearchModal-resultSubtitle :deep(mark) {
  background: rgba(255, 220, 126, 0.55);
  color: inherit;
  padding: 0 2px;
  border-radius: 4px;
}

.SearchModal-footer {
  padding-top: 4px;
}

.SearchModal-fullPage {
  width: 100%;
  min-height: 44px;
  border: 1px dashed #c6d2de;
  border-radius: 12px;
  background: #fafcfd;
  color: #4d698e;
  font-weight: 700;
}

.SearchModal-fullPage:hover,
.SearchModal-fullPage.active {
  border-color: #4d698e;
  background: #edf3f9;
}

@media (max-width: 768px) {
  .SearchModal-content {
    min-height: 100dvh;
  }

  .SearchModal-header {
    padding-bottom: 12px;
  }

  .SearchModal-body {
    gap: 16px;
  }

  .SearchModal-input {
    font-size: 15px;
  }

  .SearchModal-tabs {
    gap: 8px;
  }

  .SearchModal-tab {
    flex: 1 1 calc(50% - 4px);
    justify-content: space-between;
  }
}
</style>
