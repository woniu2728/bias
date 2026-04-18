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
        <div
          class="search-box"
          :class="{ 'search-box--active': currentSearchQuery }"
          role="button"
          tabindex="0"
          aria-label="打开全局搜索"
          @click="openSearchModal"
          @keydown.enter.prevent="openSearchModal"
          @keydown.space.prevent="openSearchModal"
        >
          <i class="fas fa-search"></i>
          <input
            type="text"
            placeholder="搜索论坛"
            :value="searchPreviewText"
            readonly
          />
          <button
            v-if="currentSearchQuery"
            type="button"
            class="search-clear"
            aria-label="清除搜索"
            @click.stop="clearSearch"
          >
            <i class="fas fa-times-circle"></i>
          </button>
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
                      <span class="notification-entry-message" v-html="getNotificationTextHtml(notification)"></span>
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
            <div v-else class="avatar" :style="{ backgroundColor: getUserAvatarColor(authStore.user) }">
              {{ getUserInitial(authStore.user) }}
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
import { renderTwemojiText } from '@/utils/twemoji'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import GlobalSearchModal from '@/components/modals/GlobalSearchModal.vue'
import {
  buildDiscussionPath,
  buildUserPath,
  formatRelativeTime,
  getUserAvatarColor,
  getUserInitial
} from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()
const route = useRoute()
const router = useRouter()

const showUserMenu = ref(false)
const showNotifications = ref(false)

const notificationItems = computed(() => notificationStore.notifications.slice(0, 8))
const hasReadNotifications = computed(() => notificationItems.value.some(notification => notification.is_read))
const currentSearchQuery = computed(() => String(route.query.q ?? route.query.search ?? '').trim())
const searchPreviewText = computed(() => currentSearchQuery.value || '')
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

  if (notification.type === 'userSuspended' || notification.type === 'userUnsuspended') {
    return '/profile'
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
    case 'discussionApproved':
      return 'fas fa-circle-check'
    case 'discussionRejected':
      return 'fas fa-circle-xmark'
    case 'postApproved':
      return 'fas fa-check'
    case 'postRejected':
      return 'fas fa-xmark'
    case 'userSuspended':
      return 'fas fa-user-lock'
    case 'userUnsuspended':
      return 'fas fa-user-check'
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
    case 'discussionApproved':
      return `${fromUser} 通过了你的讨论`
    case 'discussionRejected':
      return `${fromUser} 拒绝了你的讨论`
    case 'postApproved':
      return `${fromUser} 通过了你的回复`
    case 'postRejected':
      return `${fromUser} 拒绝了你的回复`
    case 'userSuspended':
      return `${fromUser} 封禁了你的账号`
    case 'userUnsuspended':
      return `${fromUser} 解除了你的账号封禁`
    default:
      return notificationStore.getNotificationMessage(notification)
  }
}

function getNotificationTextHtml(notification) {
  return renderTwemojiText(getNotificationText(notification))
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
  }
)

function openSearchModal() {
  modalStore.show(
    GlobalSearchModal,
    {
      initialQuery: currentSearchQuery.value,
      initialType: String(route.query.type || 'all')
    },
    {
      size: 'large',
      className: 'Modal--search'
    }
  )
}

function handleWindowClick(e) {
  if (!e.target.closest('.user-dropdown')) {
    showUserMenu.value = false
  }
  if (!e.target.closest('.notifications-dropdown')) {
    showNotifications.value = false
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('click', handleWindowClick)
}

function clearSearch() {
  if (route.name === 'search') {
    router.push('/')
    return
  }

  if (route.query.q || route.query.search) {
    const nextQuery = { ...route.query }
    delete nextQuery.q
    delete nextQuery.search
    delete nextQuery.type
    delete nextQuery.page

    router.push({
      path: route.path,
      query: nextQuery
    })
  }
}

onBeforeUnmount(() => {
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
  cursor: pointer;
}

.search-box:focus-within,
.search-box--active {
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
  cursor: pointer;
}

.search-box input::placeholder {
  color: #999;
}

.search-clear {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #8c98a4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-clear:hover {
  background: #eef2f6;
  color: #5f7081;
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

  .notifications-menu {
    width: min(420px, calc(100vw - 24px));
    right: -8px;
  }
}
</style>
