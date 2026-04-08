<template>
  <div class="index-page">
    <div class="index-container">
      <!-- 左侧导航栏 -->
      <aside class="index-nav">
        <!-- Start a Discussion 按钮 -->
        <div class="index-nav-header">
          <button
            v-if="authStore.isAuthenticated"
            class="btn-start-discussion"
            @click="$router.push('/discussions/create')"
          >
            <i class="fas fa-edit"></i>
            发起讨论
          </button>
          <button
            v-else
            class="btn-start-discussion"
            @click="$router.push('/login')"
          >
            <i class="fas fa-edit"></i>
            发起讨论
          </button>
        </div>

        <!-- 导航列表 -->
        <nav class="index-nav-list">
          <ul>
            <li>
              <a
                href="#"
                class="nav-item"
                :class="{ active: activeNav === 'all' }"
                @click.prevent="activeNav = 'all'"
              >
                <i class="fas fa-comments"></i>
                <span>全部讨论</span>
              </a>
            </li>
            <li v-if="authStore.isAuthenticated">
              <a
                href="#"
                class="nav-item"
                @click.prevent="activeNav = 'following'"
              >
                <i class="fas fa-star"></i>
                <span>关注的</span>
              </a>
            </li>
            <li v-if="authStore.isAuthenticated">
              <router-link to="/profile" class="nav-item">
                <i class="fas fa-user"></i>
                <span>我的讨论</span>
              </router-link>
            </li>
          </ul>
        </nav>

        <!-- 标签部分 -->
        <div class="index-nav-section">
          <h4 class="index-nav-heading">标签</h4>
          <nav class="index-nav-list">
            <ul>
              <li v-for="tag in tags" :key="tag.id">
                <a
                  href="#"
                  class="nav-item tag-item"
                  @click.prevent="filterByTag(tag.id)"
                  :class="{ active: selectedTag === tag.id }"
                >
                  <span class="tag-bullet" :style="{ backgroundColor: tag.color }"></span>
                  <span>{{ tag.name }}</span>
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </aside>

      <!-- 主内容区 -->
      <main class="index-content">
        <!-- 工具栏 -->
        <div class="index-toolbar">
          <ul class="index-toolbar-view">
            <li>
              <button
                class="btn-view"
                :class="{ active: sortBy === '-created_at' }"
                @click="changeSortBy('-created_at')"
              >
                最新
              </button>
            </li>
            <li>
              <button
                class="btn-view"
                :class="{ active: sortBy === '-last_posted_at' }"
                @click="changeSortBy('-last_posted_at')"
              >
                最近回复
              </button>
            </li>
            <li>
              <button
                class="btn-view"
                :class="{ active: sortBy === '-comment_count' }"
                @click="changeSortBy('-comment_count')"
              >
                热门
              </button>
            </li>
          </ul>

          <ul class="index-toolbar-action">
            <li>
              <button class="btn-refresh" @click="loadDiscussions" title="刷新">
                <i class="fas fa-sync-alt"></i>
              </button>
            </li>
          </ul>
        </div>

        <!-- 讨论列表 -->
        <div v-if="loading" class="loading-container">
          <div class="spinner"></div>
        </div>

        <div v-else-if="discussions.length === 0" class="empty-state">
          <p>暂无讨论</p>
        </div>

        <ul v-else class="discussion-list">
          <li
            v-for="discussion in discussions"
            :key="discussion.id"
            class="discussion-list-item"
            :class="{ 'is-pinned': discussion.is_pinned }"
          >
            <div class="discussion-list-item-content">
              <!-- 用户头像 -->
              <div class="discussion-list-item-author">
                <a href="#" class="avatar-link">
                  <div class="avatar" :style="{ backgroundColor: getUserColor(discussion.user) }">
                    {{ discussion.user.username.charAt(0).toUpperCase() }}
                  </div>
                </a>
                <!-- 徽章 -->
                <div class="discussion-list-item-badges">
                  <span v-if="discussion.is_pinned" class="badge badge-pinned" title="置顶">
                    <i class="fas fa-thumbtack"></i>
                  </span>
                  <span v-if="discussion.is_locked" class="badge badge-locked" title="锁定">
                    <i class="fas fa-lock"></i>
                  </span>
                </div>
              </div>

              <!-- 主要内容 -->
              <div class="discussion-list-item-main">
                <router-link :to="`/d/${discussion.id}`" class="discussion-list-item-title">
                  {{ discussion.title }}
                </router-link>

                <ul class="discussion-list-item-info">
                  <li class="item-tags" v-if="discussion.tags && discussion.tags.length">
                    <span
                      v-for="tag in discussion.tags"
                      :key="tag.id"
                      class="tag-label"
                      :style="{ backgroundColor: tag.color }"
                    >
                      {{ tag.name }}
                    </span>
                  </li>
                  <li class="item-author">
                    <span class="username">{{ discussion.user.username }}</span>
                    发起于 {{ formatDate(discussion.created_at) }}
                  </li>
                  <li v-if="discussion.last_posted_at" class="item-last-post">
                    <i class="fas fa-reply"></i>
                    最后回复 {{ formatDate(discussion.last_posted_at) }}
                  </li>
                </ul>
              </div>

              <!-- 统计信息 -->
              <div class="discussion-list-item-stats">
                <a href="#" class="discussion-list-item-count">
                  <i class="fas fa-comment"></i>
                  <span>{{ discussion.comment_count }}</span>
                </a>
              </div>
            </div>
          </li>
        </ul>

        <!-- 加载更多 -->
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
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoute } from 'vue-router'
import api from '@/api'

const authStore = useAuthStore()
const route = useRoute()

const discussions = ref([])
const tags = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const searchQuery = ref('')
const sortBy = ref('-created_at')
const currentPage = ref(1)
const hasMore = ref(false)
const selectedTag = ref(null)
const activeNav = ref('all')

onMounted(async () => {
  if (route.query.search) {
    searchQuery.value = route.query.search
  }
  await Promise.all([loadDiscussions(), loadTags()])
})

watch(() => route.query.search, (newSearch) => {
  searchQuery.value = newSearch || ''
  currentPage.value = 1
  loadDiscussions()
})

async function loadDiscussions() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      ordering: sortBy.value
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    if (selectedTag.value) {
      params.tag = selectedTag.value
    }

    const data = await api.get('/discussions/', { params })
    discussions.value = data.data || data.results || data
    hasMore.value = data.page * data.limit < data.total
  } catch (error) {
    console.error('加载讨论失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  try {
    const data = await api.get('/tags')
    tags.value = data.results || data
  } catch (error) {
    console.error('加载标签失败:', error)
  }
}

function filterByTag(tagId) {
  selectedTag.value = selectedTag.value === tagId ? null : tagId
  currentPage.value = 1
  loadDiscussions()
}

function changeSortBy(sort) {
  sortBy.value = sort
  currentPage.value = 1
  loadDiscussions()
}

async function loadMore() {
  loadingMore.value = true
  currentPage.value++
  try {
    const params = {
      page: currentPage.value,
      ordering: sortBy.value
    }
    if (selectedTag.value) {
      params.tag = selectedTag.value
    }

    const data = await api.get('/discussions/', { params })
    discussions.value.push(...(data.data || data.results || data))
    hasMore.value = data.page * data.limit < data.total
  } catch (error) {
    console.error('加载更多失败:', error)
  } finally {
    loadingMore.value = false
  }
}

function getUserColor(user) {
  const colors = ['#4D698E', '#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6']
  const index = user.id % colors.length
  return colors[index]
}

function formatDate(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 30) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
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
  padding: 10px 16px;
  background: #E7672E;
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
}

.btn-start-discussion:hover {
  background: #D85B1E;
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
  gap: 12px;
  padding: 10px 16px;
  color: #555;
  text-decoration: none;
  transition: all 0.15s;
  font-size: 14px;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  border-radius: 3px;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: #f5f8fa;
  color: #333;
  text-decoration: none;
}

.nav-item.active {
  background: #4D698E;
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

/* ========== 主内容区 ========== */
.index-content {
  flex: 1;
  background: white;
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
  background: #4D698E;
  color: white;
}

.btn-refresh {
  background: none;
  border: none;
  color: #999;
  font-size: 14px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 3px;
  transition: all 0.15s;
}

.btn-refresh:hover {
  background: #f5f8fa;
  color: #555;
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

.discussion-list-item.is-pinned {
  background: #fffbf0;
}

.discussion-list-item.is-pinned:hover {
  background: #fff8e1;
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

.discussion-list-item-title {
  display: block;
  font-size: 16px;
  font-weight: normal;
  color: #333;
  margin: 0 0 3px;
  line-height: 1.3;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discussion-list-item-title:hover {
  color: #4D698E;
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
  border-top-color: #4D698E;
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
