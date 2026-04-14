<template>
  <header class="header">
    <div class="container">
      <div class="header-left">
        <div class="logo">
          <router-link to="/">
            <img
              v-if="forumStore.settings.logo_url"
              :src="forumStore.settings.logo_url"
              :alt="forumStore.settings.forum_title"
              class="logo-image"
            />
            <span v-else>{{ forumStore.settings.forum_title }}</span>
          </router-link>
        </div>
      </div>

      <div class="header-right">
        <!-- 搜索框 -->
        <div class="search-box">
          <i class="fas fa-search"></i>
          <input
            type="text"
            placeholder="搜索论坛"
            v-model="searchQuery"
            @focus="openSearchDropdown"
            @keydown.down.prevent="moveSearchSelection(1)"
            @keydown.up.prevent="moveSearchSelection(-1)"
            @keydown.enter.prevent="submitSearchSelection"
            @keydown.esc.prevent="closeSearchDropdown"
          />

          <div v-if="showSearchDropdown" class="search-dropdown">
            <div v-if="searchLoading" class="search-status">搜索中...</div>
            <div v-else-if="searchQuery.trim() && !searchItems.length" class="search-status">
              没有找到相关内容
            </div>
            <template v-else-if="searchItems.length">
              <div
                v-for="section in searchSections"
                :key="section.key"
                class="search-section"
              >
                <div v-if="section.items.length" class="search-section-title">{{ section.label }}</div>
                <button
                  v-for="item in section.items"
                  :key="item.key"
                  type="button"
                  class="search-result"
                  :class="{ active: activeSearchIndex === item.index }"
                  @mousedown.prevent="selectSearchItem(item)"
                >
                  <span class="search-result-icon">
                    <i :class="item.icon"></i>
                  </span>
                  <span class="search-result-main">
                    <span class="search-result-title">{{ item.title }}</span>
                    <span v-if="item.subtitle" class="search-result-subtitle">{{ item.subtitle }}</span>
                  </span>
                </button>
              </div>
              <button
                type="button"
                class="search-all"
                :class="{ active: activeSearchIndex === searchItems.length }"
                @mousedown.prevent="handleSearch"
              >
                搜索 “{{ searchQuery.trim() }}”
              </button>
            </template>
            <div v-else class="search-status">输入关键词搜索讨论、帖子和用户</div>
          </div>
        </div>

        <template v-if="authStore.isAuthenticated">
          <!-- 通知 -->
          <div class="notifications-dropdown" :class="{ 'is-open': showNotifications }">
            <button
              type="button"
              class="header-icon"
              :class="{ 'has-unread': notificationStore.unreadCount > 0 }"
              :aria-expanded="showNotifications"
              @click.stop="toggleNotifications"
            >
              <i class="fas fa-bell"></i>
              <span v-if="notificationStore.unreadCount > 0" class="badge">
                {{ notificationStore.unreadCount }}
              </span>
            </button>

            <div v-if="showNotifications" class="notifications-menu">
              <div class="notifications-menu-header">
                <span>通知</span>
                <div class="notifications-menu-actions">
                  <button
                    type="button"
                    class="notifications-menu-action"
                    title="全部标记为已读"
                    :disabled="notificationStore.unreadCount === 0 || notificationStore.loading"
                    @click.stop="markAllNotificationsAsRead"
                  >
                    <i class="fas fa-check"></i>
                  </button>
                  <button
                    type="button"
                    class="notifications-menu-action"
                    title="清除已读通知"
                    :disabled="!hasReadNotifications || notificationStore.loading"
                    @click.stop="clearReadNotifications"
                  >
                    <i class="fas fa-trash-alt"></i>
                  </button>
                </div>
              </div>

              <div v-if="notificationStore.loading" class="notifications-menu-state">
                加载中...
              </div>
              <div v-else-if="!notificationItems.length" class="notifications-menu-state notifications-menu-state--empty">
                No Notifications
              </div>
              <div v-else class="notifications-menu-list">
                <section
                  v-for="group in notificationGroups"
                  :key="group.key"
                  class="notification-group"
                >
                  <button
                    type="button"
                    class="notification-group-header"
                    @click="openNotificationGroup(group)"
                  >
                    {{ group.title }}
                  </button>

                  <button
                    v-for="notification in group.items"
                    :key="notification.id"
                    type="button"
                    class="notification-entry"
                    :class="{ 'is-read': notification.is_read }"
                    @click="handleNotificationClick(notification)"
                  >
                    <span class="notification-entry-icon">
                      <img
                        v-if="notification.from_user?.avatar_url"
                        :src="notification.from_user.avatar_url"
                        :alt="notification.from_user.display_name || notification.from_user.username"
                      />
                      <i v-else :class="getNotificationIconClass(notification.type)"></i>
                    </span>
                    <span class="notification-entry-main">
                      <span class="notification-entry-message">{{ getNotificationText(notification) }}</span>
                      <span class="notification-entry-time">{{ formatRelativeTime(notification.created_at) }}</span>
                    </span>
                    <span v-if="!notification.is_read" class="notification-entry-unread"></span>
                  </button>
                </section>
              </div>

              <div v-if="notificationItems.length" class="notifications-menu-footer">
                <button type="button" class="notifications-footer-link" @click="openNotificationsPage">
                  查看全部通知
                </button>
              </div>
            </div>
          </div>

          <!-- 用户菜单 -->
          <div class="user-dropdown" @click="toggleUserMenu">
            <img
              v-if="authStore.user?.avatar_url"
              :src="authStore.user.avatar_url"
              :alt="authStore.user?.username"
              class="avatar avatar-image"
            />
            <div v-else class="avatar">
              {{ authStore.user?.username.charAt(0).toUpperCase() }}
            </div>
            <span class="username">{{ authStore.user?.username }}</span>
            <i class="fas fa-caret-down"></i>

            <!-- 下拉菜单 -->
            <div v-if="showUserMenu" class="dropdown-menu">
              <router-link :to="profilePath()" class="dropdown-item">
                <i class="fas fa-user"></i>
                <span>个人资料</span>
              </router-link>
              <router-link to="/notifications" class="dropdown-item">
                <i class="fas fa-bell"></i>
                <span>通知</span>
              </router-link>
              <a
                v-if="authStore.user?.is_staff"
                href="/admin.html"
                class="dropdown-item admin-link"
              >
                <i class="fas fa-cog"></i>
                <span>管理后台</span>
              </a>
              <div class="dropdown-divider"></div>
              <a @click.prevent="handleLogout" class="dropdown-item">
                <i class="fas fa-sign-out-alt"></i>
                <span>登出</span>
              </a>
            </div>
          </div>
        </template>

        <template v-else>
          <router-link to="/login" class="btn-login">
            登录
          </router-link>
          <router-link to="/register" class="btn-signup">
            注册
          </router-link>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useForumStore } from '@/stores/forum'
import { useModalStore } from '@/stores/modal'
import { useNotificationStore } from '@/stores/notification'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { buildDiscussionPath, buildUserPath, formatRelativeTime } from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()
const route = useRoute()
const router = useRouter()

const showUserMenu = ref(false)
const showNotifications = ref(false)
const searchQuery = ref('')
const showSearchDropdown = ref(false)
const searchLoading = ref(false)
const searchResults = ref({ discussions: [], posts: [], users: [] })
const activeSearchIndex = ref(-1)
const syncingSearchQuery = ref(false)
let searchTimer = null
let searchRequestId = 0

const notificationItems = computed(() => notificationStore.notifications.slice(0, 8))
const hasReadNotifications = computed(() => notificationItems.value.some(notification => notification.is_read))
const notificationGroups = computed(() => {
  const groups = []
  const seen = new Map()

  for (const notification of notificationItems.value) {
    const discussionId = notification.data?.discussion_id || 0
    const key = discussionId ? `discussion-${discussionId}` : 'general'

    if (!seen.has(key)) {
      const group = {
        key,
        discussionId,
        title: notification.data?.discussion_title || forumStore.settings.forum_title || '论坛',
        items: []
      }
      seen.set(key, group)
      groups.push(group)
    }

    seen.get(key).items.push(notification)
  }

  return groups
})

function profilePath() {
  return authStore.user ? buildUserPath(authStore.user) : '/profile'
}

function toggleUserMenu() {
  showNotifications.value = false
  showUserMenu.value = !showUserMenu.value
}

async function toggleNotifications() {
  showUserMenu.value = false
  showNotifications.value = !showNotifications.value

  if (!showNotifications.value) return

  try {
    await notificationStore.fetchNotifications({ limit: 8 })
  } catch (error) {
    console.error('加载通知失败:', error)
  }
}

async function markAllNotificationsAsRead() {
  try {
    await notificationStore.markAllAsRead()
  } catch (error) {
    console.error('全部标记已读失败:', error)
  }
}

async function clearReadNotifications() {
  try {
    await notificationStore.clearReadNotifications()
  } catch (error) {
    console.error('清除已读通知失败:', error)
  }
}

async function handleNotificationClick(notification) {
  try {
    if (!notification.is_read) {
      await notificationStore.markAsRead(notification.id)
    }
  } catch (error) {
    console.error('标记通知已读失败:', error)
  }

  showNotifications.value = false
  router.push(await resolveNotificationPath(notification))
}

async function resolveNotificationPath(notification) {
  const discussionId = notification.data?.discussion_id
  const postId = notification.data?.post_id
  const postNumber = notification.data?.post_number

  if (discussionId && postNumber) {
    return `/d/${discussionId}?near=${postNumber}`
  }

  if (discussionId && postId) {
    try {
      const post = await api.get(`/posts/${postId}`)
      if (post?.number) {
        return `/d/${discussionId}?near=${post.number}`
      }
    } catch (error) {
      console.error('解析通知跳转帖子失败:', error)
    }
  }

  if (discussionId) {
    return buildDiscussionPath(discussionId)
  }

  return '/notifications'
}

function openNotificationGroup(group) {
  showNotifications.value = false
  router.push(group.discussionId ? buildDiscussionPath(group.discussionId) : '/notifications')
}

function openNotificationsPage() {
  showNotifications.value = false
  router.push('/notifications')
}

function getNotificationIconClass(type) {
  switch (type) {
    case 'discussionReply':
      return 'fas fa-reply'
    case 'postLiked':
      return 'fas fa-thumbs-up'
    case 'userMentioned':
      return 'fas fa-at'
    case 'postReply':
      return 'fas fa-comment'
    default:
      return 'fas fa-bell'
  }
}

function getNotificationText(notification) {
  const fromUser = notification.from_user?.display_name || notification.from_user?.username || '有人'

  switch (notification.type) {
    case 'discussionReply':
      return `${fromUser} 回复了你关注的讨论`
    case 'postLiked':
      return `${fromUser} 赞了你的回复`
    case 'userMentioned':
      return `${fromUser} 提到了你`
    case 'postReply':
      return `${fromUser} 回复了你的帖子`
    default:
      return notificationStore.getNotificationMessage(notification)
  }
}

function handleSearch() {
  const query = searchQuery.value.trim()
  if (!query) return

  closeSearchDropdown()
  router.push({ path: '/search', query: { q: query } })
}

async function handleLogout() {
  if (composerStore.hasUnsavedChanges) {
    const confirmed = await modalStore.confirm({
      title: '确认登出',
      message: composerStore.unsavedMessage || '你有未保存内容，确定要登出吗？',
      confirmText: '继续登出',
      cancelText: '返回',
      tone: 'danger'
    })
    if (!confirmed) return
  }

  authStore.logout()
  notificationStore.disconnect()
  showUserMenu.value = false
  router.push('/')
}

const searchItems = computed(() => [
  ...searchResults.value.discussions.map((discussion) => ({
    key: `discussion-${discussion.id}`,
    type: 'discussion',
    icon: 'far fa-comments',
    title: discussion.title,
    subtitle: `${discussion.comment_count || 0} 回复 · ${formatRelativeTime(discussion.last_posted_at || discussion.created_at)}`,
    path: buildDiscussionPath(discussion)
  })),
  ...searchResults.value.posts.map((post) => ({
    key: `post-${post.id}`,
    type: 'post',
    icon: 'far fa-comment',
    title: post.discussion_title || '帖子',
    subtitle: stripExcerpt(post.excerpt || post.content),
    path: `/d/${post.discussion_id}?near=${post.number}`
  })),
  ...searchResults.value.users.map((user) => ({
    key: `user-${user.id}`,
    type: 'user',
    icon: 'far fa-user',
    title: user.display_name || user.username,
    subtitle: `@${user.username}`,
    path: buildUserPath(user)
  }))
])

const searchSections = computed(() => {
  let index = 0
  return [
    buildSearchSection('discussions', '讨论', searchItems.value.filter(item => item.type === 'discussion'), index),
    buildSearchSection('posts', '帖子', searchItems.value.filter(item => item.type === 'post'), index += searchItems.value.filter(item => item.type === 'discussion').length),
    buildSearchSection('users', '用户', searchItems.value.filter(item => item.type === 'user'), index += searchItems.value.filter(item => item.type === 'post').length)
  ]
})

watch(searchQuery, (value) => {
  if (syncingSearchQuery.value) {
    return
  }

  const query = value.trim()
  activeSearchIndex.value = -1

  if (searchTimer) clearTimeout(searchTimer)

  if (!query) {
    searchResults.value = { discussions: [], posts: [], users: [] }
    searchLoading.value = false
    return
  }

  showSearchDropdown.value = true
  searchLoading.value = true
  searchTimer = setTimeout(() => {
    fetchSearchResults(query)
  }, 220)
})

watch(
  () => route.query.q ?? route.query.search ?? '',
  (value) => {
    syncingSearchQuery.value = true
    searchQuery.value = String(value || '')
    queueMicrotask(() => {
      syncingSearchQuery.value = false
    })
  },
  { immediate: true }
)

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (!isAuthenticated) {
      showNotifications.value = false
    }
  },
  { immediate: true }
)

watch(
  () => route.fullPath,
  () => {
    showNotifications.value = false
    showUserMenu.value = false
    closeSearchDropdown()
  }
)

async function fetchSearchResults(query) {
  const requestId = ++searchRequestId

  try {
    const data = await api.get('/search', {
      params: {
        q: query,
        type: 'all',
        limit: 5
      }
    })

    if (requestId !== searchRequestId) return

    searchResults.value = {
      discussions: data.discussions || [],
      posts: data.posts || [],
      users: data.users || []
    }
  } catch (error) {
    if (requestId === searchRequestId) {
      searchResults.value = { discussions: [], posts: [], users: [] }
    }
    console.error('搜索失败:', error)
  } finally {
    if (requestId === searchRequestId) {
      searchLoading.value = false
    }
  }
}

function openSearchDropdown() {
  showSearchDropdown.value = true
  if (searchQuery.value.trim() && !searchItems.value.length) {
    fetchSearchResults(searchQuery.value.trim())
  }
}

function closeSearchDropdown() {
  showSearchDropdown.value = false
  activeSearchIndex.value = -1
}

function moveSearchSelection(direction) {
  if (!showSearchDropdown.value) {
    showSearchDropdown.value = true
  }

  const maxIndex = searchItems.value.length
  if (maxIndex < 0) return

  activeSearchIndex.value += direction
  if (activeSearchIndex.value < 0) {
    activeSearchIndex.value = maxIndex
  } else if (activeSearchIndex.value > maxIndex) {
    activeSearchIndex.value = 0
  }
}

function submitSearchSelection() {
  if (activeSearchIndex.value >= 0 && activeSearchIndex.value < searchItems.value.length) {
    selectSearchItem(searchItems.value[activeSearchIndex.value])
    return
  }

  handleSearch()
}

function selectSearchItem(item) {
  closeSearchDropdown()
  router.push(item.path)
}

function buildSearchSection(key, label, items, startIndex) {
  return {
    key,
    label,
    items: items.map((item, offset) => ({
      ...item,
      index: startIndex + offset
    }))
  }
}

function stripExcerpt(value) {
  return (value || '').replace(/<[^>]+>/g, '').slice(0, 90)
}

// 点击外部关闭菜单
function handleWindowClick(e) {
  if (!e.target.closest('.user-dropdown')) {
    showUserMenu.value = false
  }
  if (!e.target.closest('.notifications-dropdown')) {
    showNotifications.value = false
  }
  if (!e.target.closest('.search-box')) {
    closeSearchDropdown()
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('click', handleWindowClick)
}

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (typeof window !== 'undefined') {
    window.removeEventListener('click', handleWindowClick)
  }
})
</script>

<style scoped>
.header {
  background: white;
  border-bottom: 1px solid #e3e8ed;
  position: sticky;
  top: 0;
  z-index: 100;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo a {
  display: inline-flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
  color: var(--forum-primary-color);
  letter-spacing: -0.5px;
}

.logo a:hover {
  text-decoration: none;
}

.logo-image {
  max-height: 32px;
  max-width: 180px;
  object-fit: contain;
}

.nav {
  display: flex;
  gap: 5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  color: #555;
  font-size: 14px;
  border-radius: 3px;
  transition: all 0.2s;
}

.nav-item i {
  font-size: 14px;
}

.nav-item:hover {
  background: #f5f8fa;
  color: #333;
  text-decoration: none;
}

.nav-item.router-link-active {
  color: #4d698e;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 搜索框 */
.search-box {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #f5f8fa;
  border-radius: 3px;
  border: 1px solid transparent;
  transition: all 0.2s;
  width: 200px;
}

.search-box:focus-within {
  background: white;
  border-color: var(--forum-primary-color);
}

.search-box i {
  color: #999;
  font-size: 14px;
}

.search-box input {
  border: none;
  background: none;
  outline: none;
  font-size: 13px;
  color: #333;
  width: 100%;
}

.search-box input::placeholder {
  color: #999;
}

.search-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 360px;
  max-height: 70vh;
  overflow-y: auto;
  background: white;
  border: 1px solid #dfe5eb;
  border-radius: 4px;
  box-shadow: 0 12px 32px rgba(47, 60, 77, 0.16);
  z-index: 1000;
  padding: 8px 0;
}

.search-section {
  padding: 4px 0;
}

.search-section-title {
  padding: 8px 14px 5px;
  color: #9aa7b3;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.search-result,
.search-all {
  width: 100%;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 14px;
  text-align: left;
  cursor: pointer;
  color: #44515e;
}

.search-result:hover,
.search-result.active,
.search-all:hover,
.search-all.active {
  background: #f5f8fa;
  color: #2f3c4d;
}

.search-result-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #edf2f7;
  color: #6f7f8f;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-result-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.search-result-title,
.search-result-subtitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result-title {
  color: #2f3c4d;
  font-size: 13px;
  font-weight: 600;
}

.search-result-subtitle {
  color: #7f8b96;
  font-size: 12px;
  line-height: 1.35;
}

.search-all {
  border-top: 1px solid #edf1f5;
  margin-top: 5px;
  color: var(--forum-primary-color);
  font-weight: 600;
  justify-content: center;
}

.search-status {
  padding: 16px 14px;
  color: #7f8b96;
  font-size: 13px;
}

/* 发帖按钮 */
.btn-compose {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 15px;
  background: #4d698e;
  color: white;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-compose:hover {
  background: #3d5875;
  text-decoration: none;
}

.btn-compose i {
  font-size: 13px;
}

/* 图标按钮 */
.header-icon {
  position: relative;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  border: 0;
  background: transparent;
  color: #555;
  cursor: pointer;
  transition: background 0.2s;
}

.header-icon:hover {
  background: #f5f8fa;
}

.header-icon.has-unread {
  color: #4d698e;
}

.header-icon i {
  font-size: 16px;
}

.badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #e74c3c;
  color: white;
  border-radius: 10px;
  padding: 2px 5px;
  font-size: 10px;
  font-weight: 600;
  min-width: 16px;
  text-align: center;
  line-height: 1;
}

.notifications-dropdown {
  position: relative;
}

.notifications-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 420px;
  max-height: min(70vh, 640px);
  background: white;
  border: 1px solid #dbe2ea;
  border-radius: 6px;
  box-shadow: 0 14px 36px rgba(35, 45, 56, 0.18);
  overflow: hidden;
  z-index: 1000;
}

.notifications-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #e6ebf1;
  color: #5b6f86;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.notifications-menu-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.notifications-menu-action {
  border: 0;
  background: transparent;
  color: #73859a;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  padding: 0;
}

.notifications-menu-action:hover:not(:disabled) {
  background: #f3f6f9;
  color: #44576d;
}

.notifications-menu-state {
  padding: 32px 18px;
  color: #73859a;
  font-size: 14px;
  text-align: center;
}

.notifications-menu-state--empty {
  min-height: 156px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.notifications-menu-list {
  max-height: min(70vh, 560px);
  overflow-y: auto;
}

.notification-group {
  border-top: 1px solid #e8edf2;
  margin-top: -1px;
}

.notification-group-header {
  width: 100%;
  border: 0;
  background: transparent;
  color: #1f2d3d;
  text-align: left;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notification-group-header:hover {
  background: #f7fafc;
}

.notification-entry {
  width: 100%;
  border: 0;
  background: white;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #eef2f6;
  position: relative;
}

.notification-entry:last-child {
  border-bottom: 0;
}

.notification-entry:hover {
  background: #f7fafc;
}

.notification-entry.is-read {
  color: #7f8d9b;
}

.notification-entry-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #edf2f7;
  color: #62758a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.notification-entry-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.notification-entry-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.notification-entry-message {
  color: #2e3e50;
  font-size: 13px;
  line-height: 1.45;
}

.notification-entry.is-read .notification-entry-message {
  color: #677889;
}

.notification-entry-time {
  color: #8593a0;
  font-size: 12px;
}

.notification-entry-unread {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e36f2d;
  margin-top: 5px;
  flex-shrink: 0;
}

.notifications-menu-footer {
  border-top: 1px solid #e6ebf1;
  padding: 10px 16px 12px;
}

.notifications-footer-link {
  width: 100%;
  border: 0;
  background: transparent;
  color: #4d698e;
  font-size: 13px;
  font-weight: 600;
  padding: 0;
  text-align: center;
}

.notifications-footer-link:hover {
  color: #3f5876;
}

/* 用户下拉菜单 */
.user-dropdown {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-dropdown:hover {
  background: #f5f8fa;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--forum-primary-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.avatar-image {
  object-fit: cover;
}

.username {
  font-size: 14px;
  color: #555;
  font-weight: 500;
}

.user-dropdown i.fa-caret-down {
  font-size: 12px;
  color: #999;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  min-width: 200px;
  z-index: 1000;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 15px;
  color: #555;
  font-size: 14px;
  transition: background 0.2s;
  cursor: pointer;
}

.dropdown-item:hover {
  background: #f5f8fa;
  text-decoration: none;
}

.dropdown-item i {
  width: 16px;
  font-size: 14px;
  color: #999;
}

.dropdown-item.admin-link {
  color: #e74c3c;
}

.dropdown-item.admin-link i {
  color: #e74c3c;
}

.dropdown-divider {
  height: 1px;
  background: #e3e8ed;
  margin: 5px 0;
}

/* 登录/注册按钮 */
.btn-login,
.btn-signup {
  padding: 8px 15px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 3px;
  transition: all 0.2s;
}

.btn-login {
  color: #555;
  background: transparent;
}

.btn-login:hover {
  background: #f5f8fa;
  text-decoration: none;
}

.btn-signup {
  background: var(--forum-primary-color);
  color: white;
}

.btn-signup:hover {
  filter: brightness(0.92);
  text-decoration: none;
}

@media (max-width: 768px) {
  .nav-item span,
  .btn-compose span {
    display: none;
  }

  .username {
    display: none;
  }

  .search-box {
    width: 160px;
  }

  .search-dropdown {
    position: fixed;
    left: 12px;
    right: 12px;
    top: 64px;
    width: auto;
  }

  .notifications-menu {
    width: min(420px, calc(100vw - 24px));
    right: -8px;
  }
}
</style>
