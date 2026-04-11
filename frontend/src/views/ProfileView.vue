<template>
  <div class="profile-page">
    <div v-if="loading" class="loading-page">加载中...</div>
    <div v-else-if="!user" class="error-page">用户不存在</div>
    <div v-else>
      <!-- Hero 用户卡片 -->
      <div class="user-hero" :style="{ backgroundColor: user.color || '#4d698e' }">
        <div class="hero-background">
          <div class="container">
            <div class="user-card">
              <div class="user-avatar">
                <label
                  v-if="isOwnProfile"
                  class="avatar-uploader"
                  :class="{ disabled: avatarUploading }"
                >
                  <input
                    ref="avatarInput"
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    class="avatar-input"
                    @change="handleAvatarSelected"
                  />
                  <span class="avatar-upload-badge">
                    {{ avatarUploading ? '上传中...' : '更换头像' }}
                  </span>
                </label>
                <img
                  v-if="user.avatar_url"
                  :src="user.avatar_url"
                  :alt="user.username"
                  class="avatar-large avatar-image"
                />
                <div v-else class="avatar-large">
                  {{ user.username.charAt(0).toUpperCase() }}
                </div>
              </div>
              <div class="user-info-wrapper">
                <h1 class="user-identity">{{ user.display_name || user.username }}</h1>
                <ul class="user-badges" v-if="user.is_staff">
                  <li class="badge badge-admin">管理员</li>
                </ul>
                <ul class="user-info">
                  <li class="user-last-seen">
                    <i class="fas fa-circle" :class="{ online: isOnline }"></i>
                    {{ isOnline ? '在线' : formatLastSeen(user.last_seen_at) }}
                  </li>
                  <li>
                    <i class="fas fa-clock"></i>
                    加入于 {{ formatJoinDate(user.joined_at) }}
                  </li>
                </ul>
              </div>
              <div class="user-card-controls">
                <button v-if="isOwnProfile" @click="showEditModal = true" class="btn-control">
                  <i class="fas fa-pencil-alt"></i>
                  编辑
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 主内容区 -->
      <div class="container">
        <div class="user-page-layout">
          <!-- 侧边栏导航 -->
          <aside class="user-sidebar">
            <nav class="side-nav">
              <ul>
                <li>
                  <a
                    @click.prevent="switchTab('discussions')"
                    :class="{ active: activeTab === 'discussions' }"
                    class="nav-link"
                  >
                    <i class="fas fa-bars"></i>
                    <span>讨论</span>
                    <span class="badge-count">{{ user.discussion_count || 0 }}</span>
                  </a>
                </li>
                <li>
                  <a
                    @click.prevent="switchTab('posts')"
                    :class="{ active: activeTab === 'posts' }"
                    class="nav-link"
                  >
                    <i class="far fa-comment"></i>
                    <span>回复</span>
                    <span class="badge-count">{{ user.comment_count || 0 }}</span>
                  </a>
                </li>
              </ul>
            </nav>
          </aside>

          <!-- 主内容 -->
          <main class="user-content">
            <!-- 讨论列表 -->
            <div v-if="activeTab === 'discussions'" class="content-section">
              <div v-if="loadingDiscussions" class="loading-small">加载中...</div>
              <div v-else-if="discussions.length === 0" class="empty-state">
                <p>{{ isOwnProfile ? '你还没有发起过讨论' : '该用户还没有发起过讨论' }}</p>
              </div>
              <div v-else class="discussion-list">
                <div
                  v-for="discussion in discussions"
                  :key="discussion.id"
                  class="discussion-item"
                >
                  <div class="discussion-main">
                    <router-link :to="buildDiscussionPath(discussion)" class="discussion-title">
                      {{ discussion.title }}
                    </router-link>
                    <div class="discussion-meta">
                      <span>{{ formatDate(discussion.created_at) }}</span>
                    </div>
                  </div>
                  <div class="discussion-stats">
                    <div class="stat">
                      <i class="fas fa-comment"></i>
                      {{ discussion.comment_count }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 回复列表 -->
            <div v-if="activeTab === 'posts'" class="content-section">
              <div v-if="loadingPosts" class="loading-small">加载中...</div>
              <div v-else-if="posts.length === 0" class="empty-state">
                <p>{{ isOwnProfile ? '你还没有发表过回复' : '该用户还没有发表过回复' }}</p>
              </div>
              <div v-else class="post-list">
                <div v-for="post in posts" :key="post.id" class="post-item">
                  <div class="post-header">
                    <router-link
                      :to="buildDiscussionPath(post.discussion?.id || post.discussion_id)"
                      class="post-discussion-link"
                    >
                      <i class="fas fa-arrow-right"></i>
                      {{ post.discussion?.title || '讨论' }}
                    </router-link>
                    <span class="post-time">{{ formatDate(post.created_at) }}</span>
                  </div>
                  <div class="post-content" v-html="post.content_html || post.content"></div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>

    <!-- 编辑资料模态框 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-dialog">
        <div class="modal-header">
          <h3>编辑资料</h3>
          <button @click="showEditModal = false" class="modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>显示名称</label>
            <input
              v-model="editForm.display_name"
              type="text"
              class="form-control"
              placeholder="显示名称"
            />
          </div>

          <div class="form-group">
            <label>个人简介</label>
            <textarea
              v-model="editForm.bio"
              class="form-control"
              rows="4"
              placeholder="介绍一下自己..."
            ></textarea>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="showEditModal = false" class="btn-secondary">
            取消
          </button>
          <button @click="saveProfile" class="btn-primary" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'
import {
  buildDiscussionPath,
  formatMonth,
  formatRelativeTime,
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

const route = useRoute()
const authStore = useAuthStore()

const user = ref(null)
const discussions = ref([])
const posts = ref([])
const loading = ref(true)
const loadingDiscussions = ref(false)
const loadingPosts = ref(false)
const activeTab = ref('discussions')
const showEditModal = ref(false)
const saving = ref(false)
const avatarUploading = ref(false)
const avatarInput = ref(null)

const editForm = ref({
  display_name: '',
  bio: '',
})

const isOwnProfile = computed(() => {
  return authStore.user && user.value && authStore.user.id === user.value.id
})

const isOnline = computed(() => {
  if (!user.value?.last_seen_at) return false
  const lastSeen = new Date(user.value.last_seen_at)
  const now = new Date()
  return (now - lastSeen) < 5 * 60 * 1000 // 5分钟内
})

onMounted(async () => {
  await refreshProfile()
})

watch(() => route.params.id, async () => {
  posts.value = []
  discussions.value = []
  await refreshProfile()
})

async function refreshProfile() {
  await loadUser()
  await loadDiscussions()
}

async function loadUser() {
  loading.value = true
  try {
    const data = route.params.id
      ? await api.get(`/users/${route.params.id}`)
      : await api.get('/users/me')

    user.value = data

    editForm.value = {
      display_name: data.display_name || '',
      bio: data.bio || '',
    }
  } catch (error) {
    console.error('加载用户失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadDiscussions() {
  if (!user.value) return

  loadingDiscussions.value = true
  try {
    const data = await api.get('/discussions/', {
      params: {
        author: user.value.username,
        sort: 'newest',
        limit: 20,
      }
    })
    discussions.value = unwrapList(data).map(normalizeDiscussion)
  } catch (error) {
    console.error('加载讨论失败:', error)
  } finally {
    loadingDiscussions.value = false
  }
}

async function loadPosts() {
  if (!user.value || posts.value.length > 0) return

  loadingPosts.value = true
  try {
    const data = await api.get('/posts', {
      params: {
        author: user.value.username,
        limit: 20,
      }
    })
    posts.value = unwrapList(data).map(normalizePost)
  } catch (error) {
    console.error('加载回复失败:', error)
  } finally {
    loadingPosts.value = false
  }
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'posts' && posts.value.length === 0) {
    loadPosts()
  }
}

async function saveProfile() {
  saving.value = true
  try {
    await api.patch(`/users/${user.value.id}`, editForm.value)
    await authStore.fetchUser()
    await loadUser()
    showEditModal.value = false
  } catch (error) {
    alert('保存失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function handleAvatarSelected(event) {
  const file = event.target.files?.[0]
  if (!file || !user.value) return

  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('avatar', file)

    const updatedUser = await api.post(`/users/${user.value.id}/avatar`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    user.value = updatedUser
    editForm.value = {
      display_name: updatedUser.display_name || '',
      bio: updatedUser.bio || '',
    }
    await authStore.fetchUser()
  } catch (error) {
    alert('头像上传失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    avatarUploading.value = false
    if (avatarInput.value) {
      avatarInput.value.value = ''
    }
  }
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}

function formatJoinDate(dateString) {
  return formatMonth(dateString)
}

function formatLastSeen(dateString) {
  if (!dateString) return '从未'
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚活跃'
  if (minutes < 60) return `${minutes}分钟前活跃`
  if (hours < 24) return `${hours}小时前活跃`
  if (days < 30) return `${days}天前活跃`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.profile-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.loading-page,
.error-page {
  text-align: center;
  padding: 100px 20px;
  color: #aaa;
  font-size: 15px;
}

/* Hero 用户卡片 */
.user-hero {
  color: white;
  position: relative;
  margin-bottom: -20px;
}

.hero-background {
  background: linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.2));
  padding: 40px 0 60px 0;
}

.user-card {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.user-avatar {
  flex-shrink: 0;
  position: relative;
}

.avatar-large {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  border: 3px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.avatar-image {
  object-fit: cover;
  background: rgba(255, 255, 255, 0.18);
}

.avatar-uploader {
  position: absolute;
  right: -8px;
  bottom: -6px;
  z-index: 2;
  cursor: pointer;
}

.avatar-uploader.disabled {
  cursor: default;
}

.avatar-input {
  display: none;
}

.avatar-upload-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 76px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(47, 60, 77, 0.88);
  color: white;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 20px rgba(21, 32, 43, 0.2);
}

.user-info-wrapper {
  flex: 1;
  padding-top: 8px;
}

.user-identity {
  font-size: 32px;
  font-weight: 300;
  margin: 0 0 10px 0;
  display: block;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  color: white;
}

.user-badges {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
  display: flex;
  gap: 6px;
}

.user-badges li {
  display: inline-block;
}

.badge-admin {
  background: rgba(231, 76, 60, 0.95);
  color: white;
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.user-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
  opacity: 0.95;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  color: white;
}

.user-info li {
  display: inline-block;
  margin-right: 18px;
}

.user-info i {
  margin-right: 6px;
}

.user-last-seen .fa-circle {
  font-size: 8px;
  vertical-align: middle;
}

.user-last-seen .fa-circle.online {
  color: #2ecc71;
}

.user-card-controls {
  display: flex;
  align-items: flex-start;
  padding-top: 8px;
}

.btn-control {
  background: rgba(255, 255, 255, 0.15);
  border: 2px solid rgba(255, 255, 255, 0.4);
  color: white;
  padding: 9px 18px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.btn-control:hover {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.6);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.btn-control i {
  font-size: 13px;
}

/* 主内容布局 */
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.user-page-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 25px;
  padding: 40px 0 30px 0;
}

/* 侧边栏导航 */
.user-sidebar {
  position: sticky;
  top: 76px;
  height: fit-content;
}

.side-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  overflow: hidden;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  color: #555;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.side-nav ul li:last-child .nav-link {
  border-bottom: none;
}

.nav-link:hover {
  background: #f8fafb;
  text-decoration: none;
  color: #333;
}

.nav-link.active {
  background: #4d698e;
  color: white;
}

.nav-link i {
  width: 18px;
  text-align: center;
  font-size: 15px;
}

.nav-link span:first-of-type {
  flex: 1;
  font-weight: 500;
}

.badge-count {
  background: rgba(0, 0, 0, 0.08);
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  min-width: 24px;
  text-align: center;
}

.nav-link.active .badge-count {
  background: rgba(255, 255, 255, 0.25);
}

/* 主内容区 */
.user-content {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.content-section {
  padding: 25px;
  min-height: 200px;
}

.loading-small {
  text-align: center;
  padding: 50px;
  color: #aaa;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #aaa;
  font-size: 15px;
}

.empty-state p {
  margin: 0;
  line-height: 1.6;
}

/* 讨论列表 */
.discussion-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.discussion-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.discussion-item:hover {
  background: #fafbfc;
  margin: 0 -25px;
  padding: 18px 25px;
}

.discussion-item:last-child {
  border-bottom: none;
}

.discussion-main {
  flex: 1;
  min-width: 0;
}

.discussion-title {
  font-size: 16px;
  color: #333;
  font-weight: 500;
  display: block;
  margin-bottom: 6px;
  line-height: 1.4;
}

.discussion-title:hover {
  color: #4d698e;
  text-decoration: none;
}

.discussion-meta {
  font-size: 13px;
  color: #aaa;
}

.discussion-stats {
  display: flex;
  gap: 15px;
  color: #aaa;
  font-size: 14px;
  padding-left: 15px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat i {
  font-size: 14px;
}

/* 回复列表 */
.post-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.post-item {
  padding: 20px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.post-item:hover {
  background: #fafbfc;
  margin: 0 -25px;
  padding: 20px 25px;
}

.post-item:last-child {
  border-bottom: none;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.post-discussion-link {
  color: #4d698e;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.post-discussion-link:hover {
  text-decoration: none;
  color: #3d5875;
}

.post-discussion-link i {
  font-size: 12px;
}

.post-time {
  font-size: 13px;
  color: #aaa;
}

.post-content {
  color: #555;
  line-height: 1.7;
  font-size: 15px;
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background: white;
  border-radius: 3px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e3e8ed;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.modal-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
}

.modal-close:hover {
  background: #f5f8fa;
  color: #333;
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #e3e8ed;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
}

.form-control:focus {
  outline: none;
  border-color: #4d698e;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: #4d698e;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #3d5875;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e3e8ed;
  color: #555;
}

.btn-secondary:hover {
  background: #d3d8dd;
}

@media (max-width: 768px) {
  .user-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .user-info-wrapper {
    text-align: center;
  }

  .user-badges {
    justify-content: center;
  }

  .user-page-layout {
    grid-template-columns: 1fr;
  }

  .user-sidebar {
    position: static;
  }
}
</style>
