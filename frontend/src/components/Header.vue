<template>
  <header class="header">
    <div class="container">
      <div class="header-left">
        <button
          type="button"
          class="mobile-nav-toggle"
          :aria-expanded="showMobileDrawer"
          :aria-label="mobileLeftActionLabel"
          @click.stop="handleMobileLeftAction"
        >
          <i :class="mobileLeftActionIcon"></i>
        </button>
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

      <div class="mobile-header-title">
        {{ mobilePageTitle }}
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

        <button
          v-if="showMobileRightAction"
          type="button"
          class="mobile-primary-action"
          :aria-label="mobileRightActionLabel"
          @click="handleMobileRightAction"
        >
          <i :class="mobileRightActionIcon"></i>
        </button>

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
          <button type="button" class="btn-login" @click="openLogin">
            登录
          </button>
          <button type="button" class="btn-signup" @click="openRegister">
            注册
          </button>
        </template>
      </div>
    </div>

    <transition name="mobile-drawer-fade">
      <div
        v-if="showMobileDrawer"
        class="mobile-drawer-backdrop"
        @click="closeMobileDrawer"
      ></div>
    </transition>

    <aside class="mobile-drawer" :class="{ 'is-open': showMobileDrawer }">
      <div class="mobile-drawer-header">
        <router-link
          to="/"
          class="mobile-drawer-brand"
          @click="closeMobileDrawer"
        >
          <img
            v-if="forumStore.settings.logo_url"
            :src="forumStore.settings.logo_url"
            :alt="forumStore.settings.forum_title"
            class="mobile-drawer-logo"
          />
          <span v-else>{{ forumStore.settings.forum_title }}</span>
        </router-link>
        <button
          type="button"
          class="mobile-drawer-close"
          aria-label="关闭导航菜单"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="mobile-drawer-section">
        <button type="button" class="mobile-drawer-search" @click="openSearchFromDrawer">
          <i class="fas fa-search"></i>
          <span>{{ currentSearchQuery ? `搜索：${currentSearchQuery}` : '搜索论坛' }}</span>
        </button>

        <button
          v-if="authStore.canStartDiscussion"
          type="button"
          class="mobile-drawer-compose"
          @click="startDiscussionFromDrawer"
        >
          <i class="fas fa-pen-to-square"></i>
          <span>发起讨论</span>
        </button>
      </div>

      <nav class="mobile-drawer-nav">
        <router-link
          to="/"
          class="mobile-drawer-link"
          :class="{ active: isMobileNavActive('home') }"
          @click="closeMobileDrawer"
        >
          <i class="far fa-comments"></i>
          <span>全部讨论</span>
        </router-link>
        <router-link
          v-if="authStore.isAuthenticated"
          to="/following"
          class="mobile-drawer-link"
          :class="{ active: isMobileNavActive('following') }"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-bell"></i>
          <span>关注中</span>
        </router-link>
        <router-link
          to="/tags"
          class="mobile-drawer-link"
          :class="{ active: isMobileNavActive('tags') }"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-th-large"></i>
          <span>标签</span>
        </router-link>
        <router-link
          v-if="authStore.isAuthenticated"
          :to="profilePath()"
          class="mobile-drawer-link"
          :class="{ active: isMobileNavActive('profile') }"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-user"></i>
          <span>我的主页</span>
        </router-link>
        <router-link
          v-if="authStore.isAuthenticated"
          to="/notifications"
          class="mobile-drawer-link"
          :class="{ active: isMobileNavActive('notifications') }"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-bell"></i>
          <span>通知</span>
          <span v-if="notificationStore.unreadCount > 0" class="mobile-drawer-badge">
            {{ notificationStore.unreadCount }}
          </span>
        </router-link>
      </nav>

      <div v-if="authStore.isAuthenticated" class="mobile-drawer-user">
        <div class="mobile-drawer-userCard">
          <img
            v-if="authStore.user?.avatar_url"
            :src="authStore.user.avatar_url"
            :alt="authStore.user?.username"
            class="avatar avatar-image"
          />
          <div v-else class="avatar" :style="{ backgroundColor: getUserAvatarColor(authStore.user) }">
            {{ getUserInitial(authStore.user) }}
          </div>
          <div class="mobile-drawer-userMeta">
            <strong>{{ authStore.user?.display_name || authStore.user?.username }}</strong>
            <span>@{{ authStore.user?.username }}</span>
          </div>
        </div>
        <a
          v-if="authStore.user?.is_staff"
          href="/admin.html"
          class="mobile-drawer-link"
          @click="closeMobileDrawer"
        >
          <i class="fas fa-cog"></i>
          <span>管理后台</span>
        </a>
        <button type="button" class="mobile-drawer-link mobile-drawer-link--danger" @click="logoutFromDrawer">
          <i class="fas fa-sign-out-alt"></i>
          <span>登出</span>
        </button>
      </div>

      <div v-else class="mobile-drawer-auth">
        <button type="button" class="btn-login" @click="openLoginFromDrawer">登录</button>
        <button type="button" class="btn-signup" @click="openRegisterFromDrawer">注册</button>
      </div>
    </aside>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useForumStore } from '@/stores/forum'
import { useModalStore } from '@/stores/modal'
import { useNotificationStore } from '@/stores/notification'
import { renderTwemojiText } from '@/utils/twemoji'
import { openLoginModal, openRegisterModal } from '@/utils/authModal'
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
const showMobileDrawer = ref(false)
const mobileHeaderOverride = ref(null)

const notificationItems = computed(() => notificationStore.notifications.slice(0, 8))
const hasReadNotifications = computed(() => notificationItems.value.some(notification => notification.is_read))
const currentSearchQuery = computed(() => String(route.query.q ?? route.query.search ?? '').trim())
const searchPreviewText = computed(() => currentSearchQuery.value || '')
const isOwnProfileRoute = computed(() => {
  if (!authStore.user) return false

  return route.name === 'profile'
    || (route.name === 'user-profile' && String(route.params.id) === String(authStore.user.id))
})
const mobilePageTitle = computed(() => {
  if (mobileHeaderOverride.value?.title) {
    return mobileHeaderOverride.value.title
  }

  switch (route.name) {
    case 'home':
      return '全部讨论'
    case 'following':
      return '关注中'
    case 'tags':
      return '标签'
    case 'profile':
    case 'user-profile':
      return '个人主页'
    case 'notifications':
      return '通知'
    case 'search':
      return '搜索结果'
    case 'discussion-detail':
      return '讨论详情'
    case 'login':
      return '登录'
    case 'register':
      return '注册'
    default:
      return forumStore.settings.forum_title || 'Bias'
  }
})
const mobileLeftActionIcon = computed(() => mobileHeaderOverride.value?.leftAction === 'back' ? 'fas fa-angle-left' : 'fas fa-bars')
const mobileLeftActionLabel = computed(() => mobileHeaderOverride.value?.leftAction === 'back' ? '返回上一页' : '打开导航菜单')
const mobileRightActionType = computed(() => {
  if (mobileHeaderOverride.value?.rightAction) {
    return mobileHeaderOverride.value.rightAction
  }

  if (!authStore.isAuthenticated) return 'login'
  return authStore.canStartDiscussion ? 'compose-discussion' : 'none'
})
const showMobileRightAction = computed(() => mobileRightActionType.value !== 'none')
const mobileRightActionIcon = computed(() => {
  switch (mobileRightActionType.value) {
    case 'discussion-menu':
      return 'fas fa-ellipsis-v'
    case 'login':
      return 'fas fa-right-to-bracket'
    default:
      return 'fas fa-pen-to-square'
  }
})
const mobileRightActionLabel = computed(() => {
  switch (mobileRightActionType.value) {
    case 'discussion-menu':
      return '讨论操作菜单'
    case 'login':
      return '登录'
    default:
      return '发起讨论'
  }
})
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

function isMobileNavActive(key) {
  if (key === 'home') {
    return route.name === 'home' || route.name === 'tag-detail'
  }

  if (key === 'profile') {
    return isOwnProfileRoute.value
  }

  return route.name === key
}

function toggleUserMenu() {
  showNotifications.value = false
  showUserMenu.value = !showUserMenu.value
}

function toggleMobileDrawer() {
  showUserMenu.value = false
  showNotifications.value = false
  showMobileDrawer.value = !showMobileDrawer.value
}

function closeMobileDrawer() {
  showMobileDrawer.value = false
}

function handleMobileLeftAction() {
  if (mobileHeaderOverride.value?.leftAction === 'back') {
    if (window.history.length > 1) {
      router.back()
      return
    }

    router.push('/')
    return
  }

  toggleMobileDrawer()
}

function handleMobileRightAction() {
  switch (mobileRightActionType.value) {
    case 'discussion-menu':
      window.dispatchEvent(new CustomEvent('bias:mobile-header-action', {
        detail: { action: 'discussion-menu' }
      }))
      return
    case 'login':
      openLogin()
      return
    default:
      startDiscussionFromHeader()
  }
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

function startDiscussionFromHeader() {
  if (!authStore.canStartDiscussion) return
  composerStore.openDiscussionComposer({
    source: `header:${String(route.name || 'unknown')}`
  })
}

function startDiscussionFromDrawer() {
  closeMobileDrawer()
  startDiscussionFromHeader()
}

function openSearchFromDrawer() {
  closeMobileDrawer()
  openSearchModal()
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
    showMobileDrawer.value = false
    if (route.name !== 'discussion-detail') {
      mobileHeaderOverride.value = null
    }
  }
)

function handleMobileHeaderUpdate(event) {
  mobileHeaderOverride.value = event.detail || null
}

function handleMobileHeaderReset() {
  mobileHeaderOverride.value = null
}

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

function openLogin() {
  openLoginModal({ redirectPath: route.fullPath })
}

function openRegister() {
  openRegisterModal({ redirectPath: route.fullPath })
}

function openLoginFromDrawer() {
  closeMobileDrawer()
  openLogin()
}

function openRegisterFromDrawer() {
  closeMobileDrawer()
  openRegister()
}

async function logoutFromDrawer() {
  closeMobileDrawer()
  await handleLogout()
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

onMounted(() => {
  if (typeof window === 'undefined') return
  window.addEventListener('bias:mobile-header-update', handleMobileHeaderUpdate)
  window.addEventListener('bias:mobile-header-reset', handleMobileHeaderReset)
})

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
    window.removeEventListener('bias:mobile-header-update', handleMobileHeaderUpdate)
    window.removeEventListener('bias:mobile-header-reset', handleMobileHeaderReset)
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

.mobile-nav-toggle,
.mobile-primary-action,
.mobile-header-title,
.mobile-drawer,
.mobile-drawer-backdrop {
  display: none;
}

.mobile-nav-toggle,
.mobile-primary-action,
.mobile-drawer-close {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #62758a;
  align-items: center;
  justify-content: center;
}

.mobile-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: min(320px, calc(100vw - 44px));
  padding: 16px 14px 20px;
  background: #fff;
  box-shadow: 0 18px 40px rgba(31, 45, 61, 0.22);
  transform: translateX(calc(-100% - 12px));
  transition: transform 0.22s ease;
  z-index: 121;
  overflow-y: auto;
}

.mobile-drawer.is-open {
  transform: translateX(0);
}

.mobile-drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(27, 40, 55, 0.38);
  z-index: 120;
}

.mobile-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.mobile-drawer-brand {
  min-width: 0;
  display: flex;
  align-items: center;
  color: #31465d;
  font-size: 18px;
  font-weight: 700;
  text-decoration: none;
}

.mobile-drawer-brand:hover {
  text-decoration: none;
}

.mobile-drawer-logo {
  max-width: 168px;
  max-height: 32px;
  object-fit: contain;
}

.mobile-drawer-section,
.mobile-drawer-user,
.mobile-drawer-auth {
  padding-top: 14px;
  border-top: 1px solid #e7edf3;
}

.mobile-drawer-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.mobile-drawer-search,
.mobile-drawer-compose,
.mobile-drawer-link {
  width: 100%;
  min-height: 42px;
  padding: 0 14px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.mobile-drawer-search {
  background: #f4f7fa;
  color: #5d6e81;
}

.mobile-drawer-compose {
  background: var(--forum-accent-color);
  color: #fff;
}

.mobile-drawer-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.mobile-drawer-link {
  background: transparent;
  color: #4d5f72;
  justify-content: flex-start;
}

.mobile-drawer-link.active {
  background: #edf3f8;
  color: var(--forum-primary-color);
}

.mobile-drawer-link--danger {
  color: #b54b4b;
}

.mobile-drawer-badge {
  margin-left: auto;
  min-width: 22px;
  padding: 2px 7px;
  border-radius: 999px;
  background: #e86f2d;
  color: #fff;
  font-size: 11px;
  text-align: center;
}

.mobile-drawer-user {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mobile-drawer-userCard {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 4px 6px;
}

.mobile-drawer-userMeta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mobile-drawer-userMeta strong,
.mobile-drawer-userMeta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-drawer-userMeta strong {
  color: #2b3b4d;
  font-size: 14px;
}

.mobile-drawer-userMeta span {
  color: #7a8997;
  font-size: 12px;
}

.mobile-drawer-auth {
  display: flex;
  gap: 10px;
}

.mobile-drawer-auth .btn-login,
.mobile-drawer-auth .btn-signup {
  flex: 1;
}

.mobile-drawer-fade-enter-active,
.mobile-drawer-fade-leave-active {
  transition: opacity 0.2s ease;
}

.mobile-drawer-fade-enter-from,
.mobile-drawer-fade-leave-to {
  opacity: 0;
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
  .container {
    position: relative;
    padding: 0 10px;
  }

  .header-left {
    gap: 0;
  }

  .mobile-nav-toggle,
  .mobile-primary-action {
    display: inline-flex;
  }

  .mobile-header-title {
    display: block;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    width: min(220px, calc(100vw - 120px));
    color: #de6c2b;
    font-size: 16px;
    font-weight: 400;
    line-height: 56px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    pointer-events: none;
  }

  .mobile-drawer,
  .mobile-drawer-backdrop {
    display: block;
  }

  .logo,
  .search-box,
  .notifications-dropdown,
  .user-dropdown,
  .btn-login,
  .btn-signup {
    display: none;
  }

  .header-right {
    gap: 0;
  }

  .mobile-nav-toggle:hover,
  .mobile-primary-action:hover,
  .mobile-drawer-close:hover {
    background: #f4f7fa;
  }
}
</style>
