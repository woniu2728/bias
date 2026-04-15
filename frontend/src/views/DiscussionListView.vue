<template>
  <div class="index-page">
    <div class="index-container">
      <aside class="index-nav">
        <div class="index-nav-header">
          <button
            class="btn-start-discussion"
            :class="{ 'btn-start-discussion--tag': Boolean(currentTag?.color) }"
            :style="startDiscussionButtonStyle"
            @click="handleStartDiscussion"
          >
            <i class="fas fa-edit"></i>
            发起讨论
          </button>
        </div>

        <nav class="index-nav-list">
          <ul>
            <li>
              <router-link to="/" class="nav-item" :class="{ active: isAllDiscussionsPage }">
                <i class="far fa-comments"></i>
                <span>全部讨论</span>
              </router-link>
            </li>
            <li v-if="authStore.user">
              <router-link to="/following" class="nav-item" :class="{ active: isFollowingPage }">
                <i class="fas fa-bell"></i>
                <span>关注中</span>
              </router-link>
            </li>
            <li v-if="authStore.user">
              <router-link
                :to="buildUserPath(authStore.user)"
                class="nav-item"
                :class="{ active: isOwnProfilePage }"
              >
                <i class="fas fa-user"></i>
                <span>我的主页</span>
              </router-link>
            </li>
            <li v-if="hasSidebarTagNavigation" class="nav-separator" aria-hidden="true"></li>
            <li v-if="hasSidebarTagNavigation">
              <router-link to="/tags" class="nav-item" :class="{ active: isTagsPage }">
                <i class="fas fa-th-large"></i>
                <span>标签</span>
              </router-link>
            </li>
            <li v-for="tag in sidebarPrimaryTagItems" :key="`tag-${tag.id}`">
              <router-link
                :to="buildTagPath(tag)"
                class="nav-item tag-link"
                :class="{
                  active: isSidebarTagActive(tag),
                  'tag-link--child': Boolean(tag.parent_id)
                }"
                :style="getSidebarTagStyle(tag)"
                :title="tag.description || undefined"
              >
                <span class="tag-link-icon" :class="{ 'tag-link-icon--placeholder': !tag.icon }" aria-hidden="true">
                  <i v-if="tag.icon" :class="tag.icon"></i>
                  <span v-else class="tag-icon-box"></span>
                </span>
                <span class="tag-link-label">{{ tag.name }}</span>
              </router-link>
            </li>
            <li v-for="tag in sidebarSecondaryTagItems" :key="`secondary-${tag.id}`">
              <router-link
                :to="buildTagPath(tag)"
                class="nav-item tag-link"
                :class="{ active: isSidebarTagActive(tag) }"
                :style="getSidebarTagStyle(tag)"
                :title="tag.description || undefined"
              >
                <span class="tag-link-icon" :class="{ 'tag-link-icon--placeholder': !tag.icon }" aria-hidden="true">
                  <i v-if="tag.icon" :class="tag.icon"></i>
                  <span v-else class="tag-icon-box"></span>
                </span>
                <span class="tag-link-label">{{ tag.name }}</span>
              </router-link>
            </li>
            <li v-if="showMoreTagsLink">
              <router-link to="/tags" class="nav-item nav-item--muted">
                <i class="fas fa-ellipsis-h"></i>
                <span>更多标签</span>
              </router-link>
            </li>
          </ul>
        </nav>
      </aside>

      <main class="index-content">
        <section v-if="isFollowingPage" class="tag-hero following-hero">
          <div class="tag-hero-inner">
            <div class="tag-hero-pill following-pill">
              <i class="fas fa-bell"></i>
              关注中
            </div>
            <h1>关注的讨论</h1>
            <p>这里会显示你已关注、并在后续收到新回复通知的讨论。</p>
          </div>
        </section>

        <section v-if="currentTag" class="tag-hero" :style="{ '--tag-color': currentTag.color }">
          <div class="tag-hero-inner">
            <div class="tag-hero-pill">
              <span class="tag-bullet large" :style="{ backgroundColor: currentTag.color }"></span>
              {{ currentTag.name }}
            </div>
            <h1>{{ currentTag.name }}</h1>
            <p>{{ currentTag.description || '这个标签下的讨论会集中显示在这里。' }}</p>
          </div>
        </section>

        <div class="index-toolbar">
          <ul class="index-toolbar-view">
            <li>
              <button class="btn-view" :class="{ active: sortBy === 'latest' }" @click="changeSortBy('latest')">
                最新活跃
              </button>
            </li>
            <li>
              <button class="btn-view" :class="{ active: sortBy === 'newest' }" @click="changeSortBy('newest')">
                新主题
              </button>
            </li>
            <li>
              <button class="btn-view" :class="{ active: sortBy === 'top' }" @click="changeSortBy('top')">
                热门
              </button>
            </li>
          </ul>

          <ul class="index-toolbar-action">
            <li v-if="authStore.isAuthenticated">
              <button
                class="btn-mark-read"
                @click="markAllAsRead"
                :disabled="markingAllRead"
                title="全部标记为已读"
              >
                <i class="fas fa-check-double"></i>
              </button>
            </li>
            <li>
              <button class="btn-refresh" @click="refreshPageData" title="刷新">
                <i class="fas fa-sync-alt"></i>
              </button>
            </li>
          </ul>
        </div>

        <div v-if="loading" class="loading-container">
          <div class="spinner"></div>
        </div>

        <div v-else-if="discussions.length === 0" class="empty-state">
          <p>{{ emptyStateText }}</p>
        </div>

        <ul v-else class="discussion-list">
          <li
            v-for="discussion in discussions"
            :key="discussion.id"
            class="discussion-list-item"
            :class="{ 'is-sticky': discussion.is_sticky, 'is-unread': discussion.is_unread }"
          >
            <div class="discussion-list-item-content">
              <div class="discussion-list-item-author">
                <router-link :to="buildUserPath(discussion.user)" class="avatar-link">
                  <img
                    v-if="discussion.user?.avatar_url"
                    :src="discussion.user.avatar_url"
                    :alt="getUserDisplayName(discussion.user)"
                    class="avatar avatar-image"
                  />
                  <div v-else class="avatar" :style="{ backgroundColor: getUserColor(discussion.user) }">
                    {{ getUserInitial(discussion.user) }}
                  </div>
                </router-link>
                <div class="discussion-list-item-badges">
                  <span v-if="discussion.is_sticky" class="badge badge-pinned" title="置顶">
                    <i class="fas fa-thumbtack"></i>
                  </span>
                  <span v-if="discussion.is_locked" class="badge badge-locked" title="锁定">
                    <i class="fas fa-lock"></i>
                  </span>
                </div>
              </div>

              <div class="discussion-list-item-main">
                <div class="discussion-title-row">
                  <router-link :to="buildDiscussionPath(discussion)" class="discussion-list-item-title">
                    {{ discussion.title }}
                  </router-link>
                  <span v-if="discussion.approval_status === 'pending'" class="approval-pill">待审核</span>
                  <span v-if="discussion.is_unread" class="unread-pill">{{ discussion.unread_count }} 条未读</span>
                  <span v-if="discussion.is_subscribed" class="subscription-pill">已关注</span>
                </div>

                <ul class="discussion-list-item-info">
                  <li v-if="discussion.tags.length" class="item-tags">
                    <router-link
                      v-for="tag in discussion.tags"
                      :key="tag.id"
                      :to="buildTagPath(tag)"
                      class="tag-label"
                      :style="{ backgroundColor: tag.color }"
                    >
                      {{ tag.name }}
                    </router-link>
                  </li>
                  <li class="item-author">
                    <router-link :to="buildUserPath(discussion.user)" class="username">
                      {{ discussion.user?.display_name || discussion.user?.username }}
                    </router-link>
                    发起于 {{ formatRelativeTime(discussion.created_at) }}
                  </li>
                  <li v-if="discussion.last_posted_at" class="item-last-post">
                    <i class="fas fa-reply"></i>
                    最后回复 {{ formatRelativeTime(discussion.last_posted_at) }}
                  </li>
                </ul>
              </div>

              <div class="discussion-list-item-stats">
                <span class="discussion-list-item-count">
                  <i class="far fa-comment"></i>
                  <span>{{ discussion.comment_count }}</span>
                </span>
              </div>
            </div>
          </li>
        </ul>

        <div v-if="hasMore" class="load-more">
          <button class="btn btn-default" @click="loadMore" :disabled="loadingMore">
            {{ loadingMore ? '加载中...' : '加载更多' }}
          </button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useModalStore } from '@/stores/modal'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import {
  buildDiscussionPath,
  buildTagPath,
  buildUserPath,
  flattenTags,
  formatRelativeTime,
  normalizeDiscussion,
  normalizeTag,
  unwrapList
} from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()
const route = useRoute()
const router = useRouter()

const discussions = ref([])
const tags = ref([])
const currentTag = ref(null)
const loading = ref(true)
const loadingMore = ref(false)
const sortBy = ref('latest')
const currentPage = ref(1)
const total = ref(0)
const markingAllRead = ref(false)

const currentTagSlug = computed(() => route.params.slug || null)
const searchQuery = computed(() => route.query.search?.toString().trim() || '')
const hasMore = computed(() => currentPage.value * 20 < total.value)
const isFollowingPage = computed(() => route.name === 'following')
const isTagsPage = computed(() => route.name === 'tags')
const isAllDiscussionsPage = computed(() => route.name === 'home' && !currentTagSlug.value)
const isOwnProfilePage = computed(() => {
  if (!authStore.user) return false

  return (
    route.name === 'profile'
    || (route.name === 'user-profile' && String(route.params.id) === String(authStore.user.id))
  )
})
const currentTagContextParent = computed(() => findSidebarContextParent(currentTagSlug.value, tags.value))
const sidebarPrimaryTagItems = computed(() => buildSidebarPrimaryTagItems(tags.value, currentTagContextParent.value))
const sidebarSecondaryTagItems = computed(() => buildSidebarSecondaryTagItems(tags.value))
const hasSidebarTagNavigation = computed(() => tags.value.length > 0)
const showMoreTagsLink = computed(() => sidebarSecondaryTagItems.value.length > 0)
const startDiscussionButtonStyle = computed(() => getStartDiscussionButtonStyle(currentTag.value))
const emptyStateText = computed(() => {
  if (isFollowingPage.value) {
    return '你还没有关注任何讨论。'
  }
  if (currentTag.value) {
    return '这个标签下还没有讨论。'
  }
  return '暂无讨论。'
})

onMounted(async () => {
  await refreshPageData()
  window.addEventListener('pyflarum:discussion-read-state-updated', handleDiscussionReadStateUpdated)
})

onBeforeUnmount(() => {
  window.removeEventListener('pyflarum:discussion-read-state-updated', handleDiscussionReadStateUpdated)
})

watch(
  () => [route.name, route.params.slug, route.query.search],
  async () => {
    currentPage.value = 1
    await refreshPageData()
  }
)

async function refreshPageData() {
  loading.value = true
  try {
    await Promise.all([loadTags(), loadCurrentTag(), loadDiscussions(false)])
  } catch (error) {
    discussions.value = []
    currentTag.value = null
    console.error('加载首页列表失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  const response = await api.get('/tags', {
    params: {
      include_children: true
    }
  })
  tags.value = unwrapList(response).map(normalizeTag)
}

async function loadCurrentTag() {
  if (!currentTagSlug.value || isFollowingPage.value) {
    currentTag.value = null
    return
  }

  try {
    const response = await api.get(`/tags/slug/${currentTagSlug.value}`)
    currentTag.value = normalizeTag(response)
  } catch (error) {
    currentTag.value = null
    console.error('加载标签详情失败:', error)
  }
}

async function loadDiscussions(append) {
  const response = await api.get('/discussions/', {
    params: {
      page: currentPage.value,
      limit: 20,
      sort: sortBy.value,
      q: searchQuery.value || undefined,
      tag: currentTagSlug.value || undefined,
      subscription: isFollowingPage.value ? 'following' : undefined
    }
  })

  const items = unwrapList(response).map(normalizeDiscussion)

  if (append) {
    discussions.value.push(...items)
  } else {
    discussions.value = items
  }

  total.value = response.total || items.length
}

async function changeSortBy(sort) {
  if (sortBy.value === sort) return
  sortBy.value = sort
  currentPage.value = 1
  loading.value = true

  try {
    await loadDiscussions(false)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  currentPage.value += 1
  try {
    await loadDiscussions(true)
  } finally {
    loadingMore.value = false
  }
}

async function markAllAsRead() {
  if (!authStore.isAuthenticated || markingAllRead.value) return

  markingAllRead.value = true
  try {
    const response = await api.post('/discussions/read-all')
    discussions.value = discussions.value.map(discussion => ({
      ...discussion,
      is_unread: false,
      unread_count: 0,
      last_read_post_number: discussion.last_post_number || discussion.last_read_post_number || 0,
      last_read_at: response.marked_all_as_read_at || discussion.last_read_at
    }))
  } catch (error) {
    console.error('标记已读失败:', error)
    await modalStore.alert({
      title: '标记已读失败',
      message: '请稍后重试',
      tone: 'danger'
    })
  } finally {
    markingAllRead.value = false
  }
}

function handleDiscussionReadStateUpdated(event) {
  const detail = event.detail || {}
  const discussionId = Number(detail.discussionId)
  if (!discussionId) return

  discussions.value = discussions.value.map(discussion => {
    if (Number(discussion.id) !== discussionId) return discussion

    const lastReadPostNumber = Math.max(
      Number(discussion.last_read_post_number || 0),
      Number(detail.lastReadPostNumber || 0)
    )
    const unreadCount = Math.max(Number(detail.unreadCount || 0), 0)

    return {
      ...discussion,
      last_read_post_number: lastReadPostNumber,
      last_read_at: detail.lastReadAt || discussion.last_read_at,
      unread_count: unreadCount,
      is_unread: unreadCount > 0
    }
  })
}

function handleStartDiscussion() {
  if (!authStore.isAuthenticated) {
    router.push('/login')
    return
  }

  composerStore.openDiscussionComposer({
    tagId: currentTag.value?.id,
    source: route.name?.toString() || 'index'
  })
}

function buildSidebarPrimaryTagItems(sourceTags, contextParent) {
  return sortForumSidebarTags(flattenTags(sourceTags)).filter(tag => {
    const position = normalizeTagPosition(tag.position)
    if (position === null) return false
    if (!tag.parent_id) return true
    return Boolean(contextParent && tag.parent_id === contextParent.id)
  })
}

function buildSidebarSecondaryTagItems(sourceTags) {
  return sortForumSidebarTags(flattenTags(sourceTags))
    .filter(tag => normalizeTagPosition(tag.position) === null)
    .slice(0, 3)
}

function sortForumSidebarTags(sourceTags) {
  const normalizedTags = unwrapList(sourceTags).map(normalizeTag)
  const tagsById = new Map(normalizedTags.map(tag => [tag.id, tag]))

  return normalizedTags.slice().sort((left, right) => {
    const leftPosition = normalizeTagPosition(left.position)
    const rightPosition = normalizeTagPosition(right.position)

    if (leftPosition === null && rightPosition === null) {
      return Number(right.discussion_count || 0) - Number(left.discussion_count || 0)
    }

    if (rightPosition === null) return -1
    if (leftPosition === null) return 1

    const leftParent = left.parent_id ? tagsById.get(left.parent_id) : null
    const rightParent = right.parent_id ? tagsById.get(right.parent_id) : null

    if (leftParent?.id === rightParent?.id) return leftPosition - rightPosition

    if (leftParent && rightParent) {
      return normalizeTagPosition(leftParent.position) - normalizeTagPosition(rightParent.position)
    }

    if (leftParent) {
      return leftParent.id === right.id
        ? 1
        : normalizeTagPosition(leftParent.position) - rightPosition
    }

    if (rightParent) {
      return rightParent.id === left.id
        ? -1
        : leftPosition - normalizeTagPosition(rightParent.position)
    }

    return 0
  })
}

function findSidebarContextParent(targetSlug, sourceTags) {
  if (!targetSlug) return null

  for (const tag of unwrapList(sourceTags).map(normalizeTag)) {
    if (tag.slug === targetSlug) return tag

    if (flattenTags(tag.children).some(child => child.slug === targetSlug)) {
      return tag
    }
  }

  return null
}

function normalizeTagPosition(position) {
  return position === null || position === undefined ? null : Number(position)
}

function getSidebarTagStyle(tag) {
  return {
    '--tag-color': tag.color || '#6c7a89'
  }
}

function getStartDiscussionButtonStyle(tag) {
  if (!tag?.color) return {}

  return {
    '--tag-button-bg': tag.color,
    '--tag-button-text': getContrastColor(tag.color)
  }
}

function getContrastColor(color) {
  const hex = String(color || '').trim().replace('#', '')
  if (!/^[\da-fA-F]{6}$/.test(hex)) return '#ffffff'

  const red = parseInt(hex.slice(0, 2), 16)
  const green = parseInt(hex.slice(2, 4), 16)
  const blue = parseInt(hex.slice(4, 6), 16)
  const brightness = (red * 299 + green * 587 + blue * 114) / 1000

  return brightness >= 150 ? '#243447' : '#ffffff'
}

function findParentTagSlug(targetSlug, sourceTags) {
  const parent = findSidebarContextParent(targetSlug, sourceTags)
  return parent?.slug || null
}

function isSidebarTagActive(tag) {
  if (currentTagSlug.value === tag.slug) return true

  const currentTagParentSlug = findParentTagSlug(currentTagSlug.value, tags.value)
  return Boolean(currentTag.value?.parent_id && currentTagParentSlug === tag.slug)
}

function getUserColor(user) {
  const colors = ['#4d698e', '#e67e22', '#3498db', '#27ae60', '#c0392b', '#8e44ad']
  const index = (user?.id || 0) % colors.length
  return colors[index]
}

function getUserDisplayName(user) {
  return user?.display_name || user?.username || '已删除用户'
}

function getUserInitial(user) {
  const source = getUserDisplayName(user).trim()
  return source ? source.charAt(0).toUpperCase() : '?'
}
</script>

<style scoped>
.index-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.index-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  gap: 0;
}

/* ========== 左侧导航 ========== */
.index-nav {
  width: 240px;
  background: white;
  border-right: 1px solid #e3e8ed;
  min-height: calc(100vh - 56px);
  position: sticky;
  top: 56px;
  align-self: flex-start;
}

.index-nav-header {
  padding: 18px 18px 12px;
}

.btn-start-discussion {
  width: 100%;
  padding: 10px 14px;
  background: var(--forum-accent-color);
  color: white;
  border: none;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.2s, background 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  line-height: 20px;
  white-space: nowrap;
  user-select: none;
}

.btn-start-discussion:hover {
  filter: brightness(0.92);
}

.btn-start-discussion--tag {
  background: var(--tag-button-bg);
  color: var(--tag-button-text);
}

.btn-start-discussion i {
  font-size: 13px;
}

.index-nav-list {
  padding: 0 18px 24px;
}

.index-nav-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.index-nav-list li {
  margin-bottom: 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0;
  color: #75808c;
  text-decoration: none;
  transition: color 0.15s ease;
  font-size: 13px;
  font-weight: normal;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  border-radius: 3px;
  margin-bottom: 0;
  line-height: 20px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
  box-shadow: none;
  min-height: 18px;
}

.nav-item:hover {
  background: none;
  color: var(--forum-primary-color);
  text-decoration: none;
}

.nav-item.active {
  background: none;
  color: var(--forum-primary-color);
  font-weight: 700;
}

.nav-item i {
  width: 16px;
  text-align: center;
  font-size: 14px;
}

.nav-separator {
  height: 1px;
  margin: 16px 0 14px;
  background: #e5ebf1;
}

.nav-item--muted {
  color: #8a95a1;
}

.nav-item--muted:hover {
  color: var(--forum-primary-color);
}

.tag-link {
  --tag-color: #6c7a89;
  color: #75808c;
}

.tag-link:hover,
.tag-link.active {
  color: var(--tag-color);
}

.tag-link-icon {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--tag-color);
  font-size: 14px;
}

.tag-link-icon--placeholder {
  color: transparent;
}

.tag-icon-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: var(--tag-color);
}

.tag-link-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-link--child {
  margin-left: 10px;
}

.tag-bullet {
  width: 12px;
  height: 12px;
  display: inline-block;
  border-radius: 999px;
  flex-shrink: 0;
  background: var(--tag-color);
}

/* ========== 主内容区 ========== */
.index-content {
  flex: 1;
  background: white;
}

.tag-hero {
  background: linear-gradient(135deg, color-mix(in srgb, var(--tag-color) 20%, white), #f8fbfd);
  border-bottom: 1px solid #e3e8ed;
}

.following-hero {
  --tag-color: var(--forum-primary-color);
}

.tag-hero-inner {
  padding: 28px 26px;
}

.tag-hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #44515e;
  margin-bottom: 12px;
}

.tag-hero h1 {
  font-size: 30px;
  font-weight: 300;
  color: #2f3c4d;
  margin-bottom: 8px;
}

.tag-hero p {
  color: #61707f;
}

.index-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 26px;
  border-bottom: 1px solid #e3e8ed;
}

.index-toolbar-view,
.index-toolbar-action {
  display: flex;
  gap: 5px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.btn-view {
  background: #e3e8ed;
  border: none;
  color: #555;
  font-size: 13px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 3px;
  transition: all 0.15s;
  font-weight: 500;
}

.btn-view:hover {
  background: #d3d8dd;
  color: #333;
}

.btn-view.active {
  background: var(--forum-primary-color);
  color: white;
}

.btn-refresh,
.btn-mark-read {
  background: none;
  border: none;
  color: #999;
  font-size: 14px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 3px;
  transition: all 0.15s;
}

.btn-refresh:hover,
.btn-mark-read:hover {
  background: #f5f8fa;
  color: #555;
}

.btn-mark-read:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ========== 讨论列表 ========== */
.discussion-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.discussion-list-item {
  border-bottom: 1px solid #e3e8ed;
  transition: background 0.2s;
}

.discussion-list-item:hover {
  background: #fafbfc;
}

.discussion-list-item.is-sticky {
  background: #fffbf0;
}

.discussion-list-item.is-sticky:hover {
  background: #fff8e1;
}

.discussion-list-item.is-unread {
  background: #f8fbff;
}

.discussion-list-item.is-unread:hover {
  background: #f1f7fd;
}

.discussion-list-item.is-unread .discussion-list-item-title {
  font-weight: 600;
  color: #2f3c4d;
}

.discussion-list-item-content {
  display: flex;
  gap: 16px;
  padding: 12px 26px 12px 26px;
  position: relative;
}

/* 头像区域 */
.discussion-list-item-author {
  position: relative;
  flex-shrink: 0;
}

.avatar-link {
  display: block;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  font-weight: 600;
}

.avatar-image {
  object-fit: cover;
}

.discussion-list-item-badges {
  position: absolute;
  top: -14px;
  left: -2px;
  display: flex;
  gap: 4px;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  font-size: 10px;
}

.badge-pinned {
  background: #FFC107;
  color: #856404;
}

.badge-locked {
  background: #999;
  color: white;
}

/* 主要内容 */
.discussion-list-item-main {
  flex: 1;
  min-width: 0;
}

.discussion-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  margin-bottom: 3px;
}

.discussion-list-item-title {
  display: block;
  font-size: 16px;
  font-weight: normal;
  color: #333;
  margin: 0;
  line-height: 1.3;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.discussion-list-item-title:hover {
  color: var(--forum-primary-color);
  text-decoration: none;
}

.discussion-list-item-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 11px;
  color: #999;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.discussion-list-item-info > li {
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-tags {
  display: flex;
  gap: 6px;
}

.tag-label {
  padding: 2px 8px;
  border-radius: 3px;
  color: white;
  font-size: 11px;
  font-weight: 500;
}

.subscription-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #edf4fb;
  color: var(--forum-primary-color);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.approval-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff3cd;
  color: #856404;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.unread-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--forum-primary-color);
  color: white;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.username {
  font-weight: bold;
  color: #666;
}

.item-last-post i {
  font-size: 10px;
}

/* 统计信息 */
.discussion-list-item-stats {
  width: 40px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.discussion-list-item-count {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #999;
  font-size: 14px;
  text-decoration: none;
}

.discussion-list-item-count:hover {
  color: #555;
  text-decoration: none;
}

/* 加载状态 */
.loading-container {
  display: flex;
  justify-content: center;
  padding: 60px 20px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e3e8ed;
  border-top-color: var(--forum-primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #999;
  font-size: 15px;
}

.load-more {
  text-align: center;
  padding: 20px;
  border-top: 1px solid #e3e8ed;
}

.btn {
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-default {
  background: #e3e8ed;
  color: #555;
}

.btn-default:hover {
  background: #d3d8dd;
}

.btn-default:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 响应式 */
@media (max-width: 768px) {
  .index-container {
    flex-direction: column;
  }

  .index-nav {
    width: 100%;
    position: static;
    min-height: auto;
    border-right: 0;
    border-bottom: 1px solid #e3e8ed;
  }

  .discussion-list-item-content {
    padding: 12px 15px;
  }

  .discussion-list-item-title {
    font-size: 14px;
  }

  .discussion-list-item-stats {
    position: absolute;
    top: 12px;
    right: 12px;
  }

  .index-nav-list {
    padding-bottom: 18px;
  }
}
</style>
