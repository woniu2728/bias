<template>
  <div class="search-page">
    <div class="search-container">
      <aside class="search-sidebar">
        <button
          class="btn-start-discussion"
          @click="handleStartDiscussion"
        >
          <i class="fas fa-edit"></i>
          发起讨论
        </button>

        <nav class="search-filters">
          <button
            v-for="item in filterItems"
            :key="item.value"
            type="button"
            class="filter-item"
            :class="{ active: searchType === item.value }"
            @click="changeType(item.value)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </nav>
      </aside>

      <main class="search-content">
        <section class="search-hero">
          <div class="search-hero-pill">全局搜索</div>
          <h1>“{{ normalizedQuery || '未输入关键词' }}”</h1>
          <p>{{ heroText }}</p>
        </section>

        <div v-if="!normalizedQuery" class="search-state">
          请输入关键词后再搜索。
        </div>
        <div v-else-if="loading" class="search-state">
          搜索中...
        </div>
        <div v-else-if="isEmpty" class="search-state">
          没有找到相关讨论、帖子或用户。
        </div>
        <template v-else>
          <section v-if="showDiscussions" class="result-section">
            <div class="section-header">
              <h2>讨论</h2>
              <button
                v-if="searchType === 'all' && discussionTotal > discussions.length"
                type="button"
                class="section-link"
                @click="changeType('discussions')"
              >
                查看全部
              </button>
            </div>
            <div class="result-list">
              <article
                v-for="discussion in discussions"
                :key="`discussion-${discussion.id}`"
                class="result-card"
                @click="$router.push(buildDiscussionPath(discussion))"
              >
                <div class="result-card-icon">
                  <i class="far fa-comments"></i>
                </div>
                <div class="result-card-main">
                  <h3>{{ discussion.title }}</h3>
                  <p>{{ stripExcerpt(discussion.excerpt) || '这个讨论没有更多摘要。' }}</p>
                  <div class="result-meta">
                    <span>{{ discussion.comment_count || 0 }} 回复</span>
                    <span>{{ formatRelativeTime(discussion.last_posted_at || discussion.created_at) }}</span>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section v-if="showPosts" class="result-section">
            <div class="section-header">
              <h2>帖子</h2>
              <button
                v-if="searchType === 'all' && postTotal > posts.length"
                type="button"
                class="section-link"
                @click="changeType('posts')"
              >
                查看全部
              </button>
            </div>
            <div class="result-list">
              <article
                v-for="post in posts"
                :key="`post-${post.id}`"
                class="result-card"
                @click="$router.push(`/d/${post.discussion_id}?near=${post.number}`)"
              >
                <div class="result-card-icon">
                  <i class="far fa-comment"></i>
                </div>
                <div class="result-card-main">
                  <h3>{{ post.discussion_title || '帖子结果' }}</h3>
                  <p>{{ stripExcerpt(post.excerpt || post.content) }}</p>
                  <div class="result-meta">
                    <span>#{{ post.number }}</span>
                    <span>{{ formatRelativeTime(post.created_at) }}</span>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section v-if="showUsers" class="result-section">
            <div class="section-header">
              <h2>用户</h2>
              <button
                v-if="searchType === 'all' && userTotal > users.length"
                type="button"
                class="section-link"
                @click="changeType('users')"
              >
                查看全部
              </button>
            </div>
            <div class="result-list">
              <article
                v-for="user in users"
                :key="`user-${user.id}`"
                class="result-card user-card"
                @click="$router.push(buildUserPath(user))"
              >
                <div class="result-card-icon user-avatar">
                  <img
                    v-if="user.avatar_url"
                    :src="user.avatar_url"
                    :alt="user.username"
                    class="user-avatar-image"
                  />
                  <span v-else>{{ (user.display_name || user.username || '?').charAt(0).toUpperCase() }}</span>
                </div>
                <div class="result-card-main">
                  <h3>{{ user.display_name || user.username }}</h3>
                  <p>{{ user.bio || `@${user.username}` }}</p>
                  <div class="result-meta">
                    <span>{{ user.discussion_count || 0 }} 讨论</span>
                    <span>{{ user.comment_count || 0 }} 回复</span>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <div v-if="searchType !== 'all' && totalPages > 1" class="pagination">
            <button type="button" class="page-btn" :disabled="page <= 1" @click="changePage(page - 1)">
              上一页
            </button>
            <span class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
            <button type="button" class="page-btn" :disabled="page >= totalPages" @click="changePage(page + 1)">
              下一页
            </button>
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import api from '@/api'
import {
  buildDiscussionPath,
  buildUserPath,
  formatRelativeTime,
  unwrapList
} from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()

const loading = ref(false)
const total = ref(0)
const discussionTotal = ref(0)
const postTotal = ref(0)
const userTotal = ref(0)
const discussions = ref([])
const posts = ref([])
const users = ref([])

const normalizedQuery = computed(() => String(route.query.q || '').trim())
const searchType = computed(() => {
  const value = String(route.query.type || 'all')
  return ['all', 'discussions', 'posts', 'users'].includes(value) ? value : 'all'
})
const page = computed(() => {
  const value = Number(route.query.page || 1)
  return Number.isFinite(value) && value > 0 ? value : 1
})
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / 20)))
const isEmpty = computed(() => !discussions.value.length && !posts.value.length && !users.value.length)
const showDiscussions = computed(() => searchType.value === 'all' || searchType.value === 'discussions')
const showPosts = computed(() => searchType.value === 'all' || searchType.value === 'posts')
const showUsers = computed(() => searchType.value === 'all' || searchType.value === 'users')
const filterItems = computed(() => [
  { value: 'all', label: '全部', count: discussionTotal.value + postTotal.value + userTotal.value },
  { value: 'discussions', label: '讨论', count: discussionTotal.value },
  { value: 'posts', label: '帖子', count: postTotal.value },
  { value: 'users', label: '用户', count: userTotal.value },
])
const heroText = computed(() => {
  if (!normalizedQuery.value) {
    return '支持在讨论、帖子和用户之间进行全局搜索。'
  }

  if (searchType.value === 'all') {
    return `共找到 ${discussionTotal.value + postTotal.value + userTotal.value} 条结果，已按讨论、帖子和用户分组展示。`
  }

  const labelMap = {
    discussions: '讨论',
    posts: '帖子',
    users: '用户',
  }
  return `当前显示 ${labelMap[searchType.value]}结果，共 ${total.value} 条。`
})

function handleStartDiscussion() {
  if (!authStore.isAuthenticated) {
    router.push('/login')
    return
  }

  composerStore.openDiscussionComposer({
    source: 'search'
  })
}

watch(
  () => [normalizedQuery.value, searchType.value, page.value],
  async () => {
    await loadResults()
  },
  { immediate: true }
)

async function loadResults() {
  if (!normalizedQuery.value) {
    total.value = 0
    discussionTotal.value = 0
    postTotal.value = 0
    userTotal.value = 0
    discussions.value = []
    posts.value = []
    users.value = []
    return
  }

  loading.value = true
  try {
    const data = await api.get('/search', {
      params: {
        q: normalizedQuery.value,
        type: searchType.value,
        page: page.value,
        limit: 20
      }
    })

    total.value = data.total || 0
    discussionTotal.value = data.discussion_total ?? (data.discussions || []).length
    postTotal.value = data.post_total ?? (data.posts || []).length
    userTotal.value = data.user_total ?? (data.users || []).length
    discussions.value = unwrapList(data.discussions || [])
    posts.value = unwrapList(data.posts || [])
    users.value = unwrapList(data.users || [])
  } catch (error) {
    console.error('加载搜索结果失败:', error)
    total.value = 0
    discussionTotal.value = 0
    postTotal.value = 0
    userTotal.value = 0
    discussions.value = []
    posts.value = []
    users.value = []
  } finally {
    loading.value = false
  }
}

function changeType(type) {
  router.push({
    path: '/search',
    query: {
      q: normalizedQuery.value,
      type,
      ...(type === 'all' ? {} : { page: 1 })
    }
  })
}

function changePage(nextPage) {
  router.push({
    path: '/search',
    query: {
      q: normalizedQuery.value,
      type: searchType.value,
      page: nextPage
    }
  })
}

function stripExcerpt(value) {
  return String(value || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()
}
</script>

<style scoped>
.search-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.search-container {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.search-sidebar {
  padding: 20px 15px;
  background: white;
  border-right: 1px solid #e3e8ed;
  min-height: calc(100vh - 56px);
}

.btn-start-discussion {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--forum-accent-color);
  color: white;
  margin-bottom: 16px;
}

.btn-start-discussion:hover {
  filter: brightness(0.92);
}

.search-filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 3px;
  background: transparent;
  color: #556270;
}

.filter-item:hover {
  background: #f5f8fa;
}

.filter-item.active {
  background: var(--forum-primary-color);
  color: white;
}

.filter-item strong {
  font-size: 12px;
}

.search-content {
  padding: 24px 28px 40px;
}

.search-hero {
  margin-bottom: 24px;
  padding: 28px 32px;
  border-radius: 14px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--forum-primary-color) 14%, white) 0%, #eef4f8 100%);
  border: 1px solid #d9e4ec;
}

.search-hero-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 12px;
}

.search-hero h1 {
  font-size: 32px;
  font-weight: 300;
  margin-bottom: 8px;
  color: #2f3c4d;
}

.search-hero p {
  color: #607080;
  max-width: 720px;
}

.search-state {
  padding: 60px 24px;
  background: white;
  border-radius: 8px;
  text-align: center;
  color: #8897a5;
}

.result-section + .result-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-header h2 {
  font-size: 20px;
  color: #24313f;
}

.section-link {
  padding: 0;
  background: transparent;
  color: var(--forum-primary-color);
  font-size: 13px;
  font-weight: 600;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  background: white;
  border: 1px solid #e1e8ef;
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.result-card:hover {
  border-color: color-mix(in srgb, var(--forum-primary-color) 28%, white);
  box-shadow: 0 8px 24px rgba(47, 60, 77, 0.08);
  transform: translateY(-1px);
}

.result-card-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--forum-primary-color) 12%, white);
  color: var(--forum-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.result-card-main {
  min-width: 0;
}

.result-card-main h3 {
  font-size: 17px;
  color: #24313f;
  margin-bottom: 6px;
}

.result-card-main p {
  color: #667684;
  line-height: 1.6;
  margin-bottom: 8px;
}

.result-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #90a0ad;
  font-size: 12px;
}

.user-card {
  align-items: center;
}

.user-avatar {
  overflow: hidden;
  font-weight: 700;
}

.user-avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}

.page-btn {
  background: white;
  border: 1px solid #d6e0e8;
  color: #44515e;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-color);
}

.page-info {
  color: #6d7c89;
  font-size: 13px;
}

@media (max-width: 900px) {
  .search-container {
    grid-template-columns: 1fr;
  }

  .search-sidebar {
    min-height: auto;
    border-right: none;
    border-bottom: 1px solid #e3e8ed;
  }
}
</style>
