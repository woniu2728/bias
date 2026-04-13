<template>
  <div class="index-page">
    <div class="index-container">
      <aside class="index-nav">
        <div class="index-nav-header">
          <button
            class="btn-start-discussion"
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
            <li>
              <router-link to="/tags" class="nav-item">
                <i class="fas fa-tags"></i>
                <span>全部标签</span>
              </router-link>
            </li>
            <li v-if="authStore.user">
              <router-link :to="buildUserPath(authStore.user)" class="nav-item">
                <i class="fas fa-user"></i>
                <span>我的主页</span>
              </router-link>
            </li>
          </ul>
        </nav>

        <div class="index-nav-section">
          <h4 class="index-nav-heading">标签</h4>
          <nav class="index-nav-list">
            <ul>
              <li v-for="tag in sidebarTags" :key="tag.id">
                <router-link
                  :to="buildTagPath(tag)"
                  class="nav-item tag-item"
                  :class="{ active: currentTagSlug === tag.slug }"
                >
                  <span class="tag-bullet" :style="{ backgroundColor: tag.color }"></span>
                  <span>{{ tag.name }}</span>
                </router-link>
              </li>
            </ul>
          </nav>
        </div>
      </aside>

      <main class="index-content">
        <section v-if="showForumHero" class="forum-hero">
          <div class="forum-hero-inner">
            <div class="forum-hero-pill">{{ forumStore.settings.forum_title }}</div>
            <h1>{{ forumStore.settings.welcome_title }}</h1>
            <p>{{ forumStore.settings.welcome_message }}</p>
          </div>
        </section>

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
                    :alt="discussion.user?.username"
                    class="avatar avatar-image"
                  />
                  <div v-else class="avatar" :style="{ backgroundColor: getUserColor(discussion.user) }">
                    {{ discussion.user?.username?.charAt(0).toUpperCase() }}
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
import { useForumStore } from '@/stores/forum'
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
const forumStore = useForumStore()
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
const sidebarTags = computed(() => flattenTags(tags.value))
const isFollowingPage = computed(() => route.name === 'following')
const isAllDiscussionsPage = computed(() => route.name === 'home' && !currentTagSlug.value)
const showForumHero = computed(() => isAllDiscussionsPage.value && !searchQuery.value)
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
    alert('标记已读失败，请稍后重试')
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

function getUserColor(user) {
  const colors = ['#4d698e', '#e67e22', '#3498db', '#27ae60', '#c0392b', '#8e44ad']
  const index = (user?.id || 0) % colors.length
  return colors[index]
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
  padding: 15px;
}

.btn-start-discussion {
  width: 100%;
  padding: 8px 13px;
  background: var(--forum-accent-color);
  color: white;
  border: none;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
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

.btn-start-discussion i {
  font-size: 13px;
}

.index-nav-list {
  padding: 0 15px;
}

.index-nav-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 15px;
  color: #555;
  text-decoration: none;
  transition: all 0.15s;
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
}

.nav-item:hover {
  background: #f5f8fa;
  color: #333;
  text-decoration: none;
}

.nav-item.active {
  background: var(--forum-primary-color);
  color: white;
}

.nav-item i {
  width: 16px;
  text-align: center;
  font-size: 14px;
}

.index-nav-section {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #e3e8ed;
}

.index-nav-heading {
  padding: 8px 15px;
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin: 0;
}

.tag-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tag-bullet {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tag-bullet.large {
  width: 12px;
  height: 12px;
}

/* ========== 主内容区 ========== */
.index-content {
  flex: 1;
  background: white;
}

.forum-hero {
  background: linear-gradient(135deg, color-mix(in srgb, var(--forum-primary-color) 16%, white), #f8fbfd);
  border-bottom: 1px solid #e3e8ed;
}

.forum-hero-inner {
  padding: 30px 26px;
}

.forum-hero-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 12px;
}

.forum-hero h1 {
  font-size: 30px;
  font-weight: 300;
  color: #2f3c4d;
  margin-bottom: 8px;
}

.forum-hero p {
  color: #61707f;
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
}
</style>
