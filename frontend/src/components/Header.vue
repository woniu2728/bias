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
        <HeaderSearchBox
          :current-search-query="currentSearchQuery"
          :search-preview-text="searchPreviewText"
          @open-search="openSearchModal"
          @clear-search="clearSearch"
        />

        <button
          v-if="showMobileRightAction"
          type="button"
          class="mobile-primary-action"
          :class="{ 'discussion-actions-scope': mobileRightActionType === 'discussion-menu' }"
          :aria-label="mobileRightActionLabel"
          @click="handleMobileRightAction"
        >
          <i :class="mobileRightActionIcon"></i>
        </button>

        <div
          v-if="showSessionPlaceholder || showAuthenticatedUi"
          class="header-account-cluster"
        >
          <div v-if="showSessionPlaceholder" class="header-session-placeholder" aria-hidden="true">
            <span class="header-session-dot"></span>
            <span class="header-session-chip"></span>
          </div>

          <template v-else>
            <!-- 通知 -->
            <HeaderNotificationsMenu
              :show-notifications="showNotifications"
              :notification-store="notificationStore"
              :notification-items="notificationItems"
              :notification-groups="notificationGroups"
              :has-read-notifications="hasReadNotifications"
              :action-message="actionMessage"
              :action-tone="actionTone"
              :marking-all-read="markingAllRead"
              :clearing-read="clearingRead"
              :get-notification-icon-class="getNotificationIconClass"
              :get-notification-text-html="getNotificationTextHtml"
              :format-relative-time="formatRelativeTime"
              @toggle="toggleNotifications"
              @mark-all-read="markAllNotificationsAsRead"
              @clear-read="clearReadNotifications"
              @open-group="openNotificationGroup"
              @notification-click="handleNotificationClick"
              @open-page="openNotificationsPage"
            />

            <!-- 用户菜单 -->
            <HeaderUserMenu
              :auth-store="authStore"
              :show-user-menu="showUserMenu"
              :profile-path="profilePath"
              :get-user-avatar-color="getUserAvatarColor"
              :get-user-initial="getUserInitial"
              @toggle="toggleUserMenu"
              @logout="handleLogout"
            />
          </template>
        </div>

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

    <HeaderMobileDrawer
      :show-mobile-drawer="showMobileDrawer"
      :auth-store="authStore"
      :forum-store="forumStore"
      :notification-store="notificationStore"
      :current-search-query="currentSearchQuery"
      :is-mobile-nav-active="isMobileNavActive"
      :profile-path="profilePath"
      :get-user-avatar-color="getUserAvatarColor"
      :get-user-initial="getUserInitial"
      @close="closeMobileDrawer"
      @open-search="openSearchFromDrawer"
      @start-discussion="startDiscussionFromDrawer"
      @logout="logoutFromDrawer"
      @open-login="openLoginFromDrawer"
      @open-register="openRegisterFromDrawer"
    />
  </header>
</template>

<script setup>
import { computed } from 'vue'
import HeaderMobileDrawer from '@/components/header/HeaderMobileDrawer.vue'
import HeaderNotificationsMenu from '@/components/header/HeaderNotificationsMenu.vue'
import HeaderSearchBox from '@/components/header/HeaderSearchBox.vue'
import HeaderUserMenu from '@/components/header/HeaderUserMenu.vue'
import { useHeaderActions } from '@/composables/useHeaderActions'
import { useHeaderMobileState } from '@/composables/useHeaderMobileState'
import { useHeaderNotifications } from '@/composables/useHeaderNotifications'
import { useHeaderUiState } from '@/composables/useHeaderUiState'
import {
  getNotificationIconClass,
  getNotificationTextHtml
} from '@/composables/useNotificationPresentation'
import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useForumStore } from '@/stores/forum'
import { useModalStore } from '@/stores/modal'
import { useNotificationStore } from '@/stores/notification'
import { useRoute, useRouter } from 'vue-router'
import {
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
const { startDiscussion } = useStartDiscussionAction({
  authStore,
  composerStore,
  router
})
const {
  showMobileDrawer,
  mobileHeaderOverride,
  mobilePageTitle,
  mobileLeftActionIcon,
  mobileLeftActionLabel,
  mobileRightActionType,
  showMobileRightAction,
  mobileRightActionIcon,
  mobileRightActionLabel,
  isMobileNavActive,
  closeMobileDrawer,
  flipMobileDrawer,
  resetMobileHeaderOverride,
  updateMobileHeaderOverride
} = useHeaderMobileState({
  authStore,
  forumTitle: forumStore.settings.forum_title || 'Bias',
  route
})
const {
  showNotifications,
  notificationItems,
  hasReadNotifications,
  notificationGroups,
  actionMessage,
  actionTone,
  markingAllRead,
  clearingRead,
  toggleNotifications,
  markAllNotificationsAsRead,
  clearReadNotifications,
  handleNotificationClick,
  openNotificationGroup,
  openNotificationsPage,
  closeNotifications
} = useHeaderNotifications({
  modalStore,
  notificationStore,
  forumTitle: forumStore.settings.forum_title || '论坛',
  router
})
const {
  openSearchModal,
  openLogin,
  openRegister,
  handleLogout,
  clearSearch
} = useHeaderActions({
  authStore,
  composerStore,
  currentSearchQuery: computed(() => String(route.query.q ?? route.query.search ?? '').trim()),
  modalStore,
  notificationStore,
  route,
  router
})
const currentSearchQuery = computed(() => String(route.query.q ?? route.query.search ?? '').trim())
const searchPreviewText = computed(() => currentSearchQuery.value || '')
const showAuthenticatedUi = computed(() => authStore.isAuthenticated && Boolean(authStore.user) && !authStore.isRestoringSession)
const showSessionPlaceholder = computed(() => authStore.isRestoringSession && authStore.isAuthenticated && !authStore.user)
const {
  showUserMenu,
  toggleUserMenu,
  openLoginFromDrawer,
  openRegisterFromDrawer,
  logoutFromDrawer
} = useHeaderUiState({
  authStore,
  closeMobileDrawer,
  closeNotifications,
  handleLogout,
  openLogin,
  openRegister,
  resetMobileHeaderOverride,
  route,
  updateMobileHeaderOverride
})

function profilePath() {
  return authStore.user ? buildUserPath(authStore.user) : '/profile'
}

function toggleMobileDrawer() {
  showUserMenu.value = false
  closeNotifications()
  flipMobileDrawer()
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

function startDiscussionFromHeader() {
  startDiscussion({
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

.header-account-cluster {
  min-width: 188px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

.header-session-placeholder {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
}

.header-session-dot,
.header-session-chip {
  display: inline-flex;
  background: linear-gradient(90deg, #eef3f7 0%, #e1e8ef 50%, #eef3f7 100%);
  background-size: 200% 100%;
  animation: headerPlaceholderPulse 1.2s ease-in-out infinite;
}

.header-session-dot {
  width: 28px;
  height: 28px;
  border-radius: 999px;
}

.header-session-chip {
  width: 84px;
  height: 16px;
  border-radius: 999px;
}

.mobile-nav-toggle,
.mobile-primary-action,
.mobile-header-title {
  display: none;
}

.mobile-nav-toggle,
.mobile-primary-action {
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

@keyframes headerPlaceholderPulse {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
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

  .logo,
  .search-box,
  .notifications-dropdown,
  .user-dropdown,
  .header-account-cluster,
  .header-session-placeholder,
  .btn-login,
  .btn-signup {
    display: none;
  }

  .header-right {
    gap: 0;
  }

  .mobile-nav-toggle:hover,
  .mobile-primary-action:hover {
    background: #f4f7fa;
  }
}
</style>
