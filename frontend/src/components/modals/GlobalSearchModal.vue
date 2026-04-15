<template>
  <div ref="root" class="Modal Modal--large Modal--search fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content SearchModal-content">
      <div class="Modal-close">
        <button
          type="button"
          class="Button Button--icon Button--link"
          aria-label="关闭搜索"
          @click="modalStore.dismiss()"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="Modal-header SearchModal-header">
        <h3>搜索</h3>
        <p>按讨论、帖子、用户快速定位内容，交互参考 Flarum 的全局搜索流程。</p>
      </div>

      <div class="Modal-body SearchModal-body">
        <div class="SearchModal-inputWrap">
          <i class="fas fa-search"></i>
          <input
            ref="inputRef"
            v-model="query"
            type="search"
            class="SearchModal-input"
            placeholder="输入关键词搜索讨论、帖子和用户"
            @keydown.down.prevent="moveSelection(1)"
            @keydown.up.prevent="moveSelection(-1)"
            @keydown.enter.prevent="submitSelection"
            @keydown.esc.prevent="modalStore.dismiss()"
          />
          <button v-if="normalizedQuery" type="button" class="SearchModal-clear" @click="clearQuery">
            <i class="fas fa-times-circle"></i>
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
          输入关键词后即可开始搜索。你可以直接回车进入完整搜索结果页。
        </div>
        <div v-else-if="loading" class="SearchModal-state">
          搜索中...
        </div>
        <div v-else-if="isEmpty" class="SearchModal-state">
          没有找到相关结果，试试更短的关键词或切换分类。
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
                  只看{{ section.label }}
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
                  <span class="SearchModal-resultIcon" :class="{ 'SearchModal-resultIcon--avatar': item.avatarUrl }">
                    <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.titleText" />
                    <i v-else :class="item.icon"></i>
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
              <span class="SearchModal-resultIcon" :class="{ 'SearchModal-resultIcon--avatar': item.avatarUrl }">
                <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.titleText" />
                <i v-else :class="item.icon"></i>
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
              查看{{ activeTabLabel }}完整结果
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
import { useModalStore } from '@/stores/modal'
import api from '@/api'
import { buildDiscussionPath, buildUserPath, formatRelativeTime, unwrapList } from '@/utils/forum'
import { highlightSearchText } from '@/utils/search'

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
const root = ref(null)
const inputRef = ref(null)
const query = ref(String(props.initialQuery || ''))
const activeType = ref(['all', 'discussions', 'posts', 'users'].includes(props.initialType) ? props.initialType : 'all')
const loading = ref(false)
const searchResults = ref({
  discussions: [],
  posts: [],
  users: [],
})
const totals = ref({
  discussions: 0,
  posts: 0,
  users: 0,
})
const activeResultIndex = ref(-1)
let searchTimer = null
let requestId = 0

const normalizedQuery = computed(() => query.value.trim())
const tabs = computed(() => [
  { value: 'all', label: '全部', count: totals.value.discussions + totals.value.posts + totals.value.users },
  { value: 'discussions', label: '讨论', count: totals.value.discussions },
  { value: 'posts', label: '帖子', count: totals.value.posts },
  { value: 'users', label: '用户', count: totals.value.users },
])
const activeTabLabel = computed(() => tabs.value.find(tab => tab.value === activeType.value)?.label || '全部')

const allDiscussionItems = computed(() => buildDiscussionItems(searchResults.value.discussions))
const allPostItems = computed(() => buildPostItems(searchResults.value.posts))
const allUserItems = computed(() => buildUserItems(searchResults.value.users))

const groupedSections = computed(() => {
  let selectIndex = 0

  return [
    { key: 'discussions', label: '讨论', items: allDiscussionItems.value },
    { key: 'posts', label: '帖子', items: allPostItems.value },
    { key: 'users', label: '用户', items: allUserItems.value },
  ]
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
  const sourceMap = {
    discussions: allDiscussionItems.value,
    posts: allPostItems.value,
    users: allUserItems.value,
  }
  const items = sourceMap[activeType.value] || []
  return items.map((item, index) => ({
    ...item,
    selectIndex: index,
  }))
})

const visibleSelectableItems = computed(() => {
  if (activeType.value === 'all') {
    return groupedSections.value.flatMap(section => section.items)
  }
  return activeItems.value
})

const fullPageActionIndex = computed(() => visibleSelectableItems.value.length)
const isEmpty = computed(() => {
  return !searchResults.value.discussions.length && !searchResults.value.posts.length && !searchResults.value.users.length
})

watch(
  () => props.showing,
  showing => {
    if (!showing) return

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
      searchResults.value = { discussions: [], posts: [], users: [] }
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
    if (!normalizedQuery.value) {
      activeResultIndex.value = -1
      return
    }

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

onMounted(() => {
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select?.()
  })
})

onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
})

async function fetchResults() {
  const currentRequestId = ++requestId

  try {
    const data = await api.get('/search', {
      params: {
        q: normalizedQuery.value,
        type: activeType.value,
        limit: activeType.value === 'all' ? 4 : 8,
      }
    })

    if (currentRequestId !== requestId) return

    totals.value = {
      discussions: data.discussion_total ?? 0,
      posts: data.post_total ?? 0,
      users: data.user_total ?? 0,
    }
    searchResults.value = {
      discussions: unwrapList(data.discussions || []),
      posts: unwrapList(data.posts || []),
      users: unwrapList(data.users || []),
    }
  } catch (error) {
    if (currentRequestId !== requestId) return

    console.error('加载搜索结果失败:', error)
    searchResults.value = { discussions: [], posts: [], users: [] }
    totals.value = { discussions: 0, posts: 0, users: 0 }
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}

function buildDiscussionItems(items) {
  return items.map(discussion => ({
    key: `discussion-${discussion.id}`,
    icon: 'far fa-comments',
    avatarUrl: discussion.user?.avatar_url || '',
    titleText: discussion.title || '讨论',
    titleHtml: highlightSearchText(discussion.title || '讨论', normalizedQuery.value, 80),
    subtitleHtml: highlightSearchText(discussion.excerpt || '这个讨论没有更多摘要。', normalizedQuery.value, 120),
    metaText: `${discussion.comment_count || 0} 回复 · ${formatRelativeTime(discussion.last_posted_at || discussion.created_at)}`,
    path: buildDiscussionPath(discussion),
  }))
}

function buildPostItems(items) {
  return items.map(post => ({
    key: `post-${post.id}`,
    icon: 'far fa-comment',
    avatarUrl: post.user?.avatar_url || '',
    titleText: post.discussion_title || '帖子',
    titleHtml: highlightSearchText(post.discussion_title || '帖子', normalizedQuery.value, 80),
    subtitleHtml: highlightSearchText(post.excerpt || post.content || '', normalizedQuery.value, 140),
    metaText: `#${post.number} · ${post.user?.display_name || post.user?.username || '未知用户'} · ${formatRelativeTime(post.created_at)}`,
    path: `/d/${post.discussion_id}?near=${post.number}`,
  }))
}

function buildUserItems(items) {
  return items.map(user => ({
    key: `user-${user.id}`,
    icon: 'far fa-user',
    avatarUrl: user.avatar_url || '',
    titleText: user.display_name || user.username || '用户',
    titleHtml: highlightSearchText(user.display_name || user.username || '用户', normalizedQuery.value, 60),
    subtitleHtml: highlightSearchText(user.bio || `@${user.username}`, normalizedQuery.value, 100),
    metaText: `${user.discussion_count || 0} 讨论 · ${user.comment_count || 0} 回复`,
    path: buildUserPath(user),
  }))
}

function clearQuery() {
  query.value = ''
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
  if (!normalizedQuery.value) return

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
  modalStore.dismiss()
  router.push(item.path)
}

function openFullResults() {
  if (!normalizedQuery.value) return

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
}

.SearchModal-clear {
  border: 0;
  background: transparent;
  color: #8a96a2;
  width: 28px;
  height: 28px;
  border-radius: 50%;
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
