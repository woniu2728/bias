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
        <component
          :is="item.component"
          v-for="item in searchHeaderItems"
          :key="item.key"
          v-bind="item.componentProps || {}"
        />

        <button
          v-if="effectiveShowMobileRightAction"
          type="button"
          class="mobile-primary-action"
          :class="{ 'discussion-actions-scope': effectiveMobileRightActionType === 'discussion-menu' }"
          :aria-label="effectiveMobileRightActionLabel"
          @click="handleMobileRightAction"
        >
          <i :class="effectiveMobileRightActionIcon"></i>
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
            <component
              :is="item.component"
              v-for="item in headerComponentItems"
              :key="item.key"
              v-bind="item.componentProps || {}"
            />
            <component
              :is="item.href ? 'a' : 'button'"
              v-for="item in headerActionItems"
              :key="item.key"
              v-bind="item.href ? { href: item.href } : { type: 'button' }"
              class="header-plugin-action"
              :title="item.description || item.label"
              @click="handleHeaderItemClick(item, $event)"
            >
              <i v-if="item.icon" :class="item.icon"></i>
              <span v-if="item.label">{{ item.label }}</span>
            </component>

            <component
              :is="item.component"
              v-for="item in userMenuHostItems"
              :key="item.key"
              v-bind="item.componentProps || {}"
            />
          </template>
        </div>

        <template v-else>
          <button
            v-for="item in guestActionItems"
            :key="item.key"
            type="button"
            :class="item.tone === 'primary' ? 'btn-signup' : 'btn-login'"
            @click="handleGuestItemClick(item, $event)"
          >
            {{ item.label }}
          </button>
        </template>
      </div>
    </div>

    <HeaderMobileDrawer
      :show-mobile-drawer="showMobileDrawer"
      :auth-store="authStore"
      :forum-store="forumStore"
      :is-mobile-nav-active="isMobileNavActive"
      :action-items="mobileDrawerActionItems"
      :user-card-items="mobileDrawerUserCardItems"
      :guest-items="mobileDrawerGuestItems"
      :personal-items="mobileDrawerPersonalItems"
      :user-items="mobileDrawerUserItems"
      @close="closeMobileDrawer"
      @item-click="handleMobileDrawerItemClick"
    />
  </header>
</template>

<script setup>
import { computed } from 'vue'
import HeaderMobileDrawer from '@/components/header/HeaderMobileDrawer.vue'
import { useHeaderActions } from '@/composables/useHeaderActions'
import { useHeaderMobileState } from '@/composables/useHeaderMobileState'
import { useHeaderUiState } from '@/composables/useHeaderUiState'
import { getHeaderItems } from '@/forum/frontendRegistry'
import { useStartDiscussionAction } from '@/forum/startDiscussionRuntime'
import { useAuthStore } from '@bias/users'
import { useComposerStore } from '@/stores/composer'
import { useForumStore } from '@/stores/forum'
import { useForumUiStore } from '@/stores/forumUi'
import { useModalStore } from '@/stores/modal'
import { useRoute, useRouter } from 'vue-router'
import {
  getUserAvatarColor,
  getUserInitial
} from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const forumUiStore = useForumUiStore()
const modalStore = useModalStore()
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
  route,
  router
})
const currentSearchQuery = computed(() => String(route.query.q ?? route.query.search ?? '').trim())
const searchPreviewText = computed(() => currentSearchQuery.value || '')
function buildHeaderExtensionContext(extra = {}) {
  return {
    authStore,
    forumStore,
    forumUiStore,
    route,
    router,
    handleLogout,
    openSearchModal,
    clearSearch,
    openLogin,
    openRegister,
    startDiscussion: startDiscussionFromHeader,
    currentSearchQuery: currentSearchQuery.value,
    searchPreviewText: searchPreviewText.value,
    showUserMenu: showUserMenu.value,
    toggleUserMenu,
    handleUserMenuItemClick,
    getUserAvatarColor,
    getUserInitial,
    ...extra,
  }
}

const afterSearchHeaderItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'after-search'))
const searchHeaderItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'search'))
const headerComponentItems = computed(() => afterSearchHeaderItems.value.filter(item => item.component))
const headerActionItems = computed(() => afterSearchHeaderItems.value.filter(item => !item.component))
const guestActionItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'guest-actions'))
const userMenuItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'user-menu'))
const userMenuHostItems = computed(() => getHeaderItems(buildHeaderExtensionContext({
  userMenuItems: userMenuItems.value,
}), 'user-menu-host'))
const mobileDrawerGuestItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'mobile-drawer-auth'))
const mobileDrawerActionItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'mobile-drawer-actions'))
const mobileDrawerUserCardItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'mobile-drawer-user-card'))
const mobileDrawerPersonalItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'mobile-drawer-personal'))
const mobileDrawerUserItems = computed(() => getHeaderItems(buildHeaderExtensionContext(), 'mobile-drawer-user'))
const mobileHeaderRightItems = computed(() => {
  if (mobileHeaderOverride.value?.rightAction) return []
  return getHeaderItems(buildHeaderExtensionContext(), 'mobile-header-right-action')
})
const mobileHeaderRightItem = computed(() => mobileHeaderRightItems.value[0] || null)
const effectiveMobileRightActionType = computed(() => mobileHeaderRightItem.value?.actionType || mobileRightActionType.value)
const effectiveShowMobileRightAction = computed(() => showMobileRightAction.value || Boolean(mobileHeaderRightItem.value))
const effectiveMobileRightActionIcon = computed(() => mobileHeaderRightItem.value?.icon || mobileRightActionIcon.value)
const effectiveMobileRightActionLabel = computed(() => mobileHeaderRightItem.value?.label || mobileRightActionLabel.value)
const showAuthenticatedUi = computed(() => authStore.isAuthenticated && Boolean(authStore.user) && !authStore.isRestoringSession)
const showSessionPlaceholder = computed(() => authStore.isRestoringSession && authStore.isAuthenticated && !authStore.user)
const {
  showUserMenu,
  toggleUserMenu
} = useHeaderUiState({
  authStore,
  closeMobileDrawer,
  closeHeaderOverlays,
  handleLogout,
  openLogin,
  openRegister,
  resetMobileHeaderOverride,
  route,
  updateMobileHeaderOverride
})

function closeHeaderOverlays(detail = {}) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('bias:header-overlays-close', {
    detail
  }))
}

function toggleMobileDrawer() {
  showUserMenu.value = false
  closeHeaderOverlays({ source: 'mobile-drawer' })
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
  if (mobileHeaderRightItem.value && !mobileHeaderOverride.value?.rightAction) {
    invokeHeaderItem(mobileHeaderRightItem.value)
    return
  }

  switch (mobileRightActionType.value) {
    case 'discussion-menu':
      window.dispatchEvent(new CustomEvent('bias:mobile-header-action', {
        detail: { action: 'discussion-menu' }
      }))
      return
    default:
  }
}

async function invokeHeaderItem(item, event, { closeUser = false, closeDrawer = false } = {}) {
  if (item.disabled) {
    event?.preventDefault?.()
    return
  }

  if (closeUser) {
    showUserMenu.value = false
  }
  if (closeDrawer) {
    closeMobileDrawer()
  }

  if (typeof item.onClick === 'function') {
    event?.preventDefault?.()
    await item.onClick(buildHeaderExtensionContext())
  }
}

function handleHeaderItemClick(item, event) {
  return invokeHeaderItem(item, event)
}

function handleGuestItemClick(item, event) {
  return invokeHeaderItem(item, event)
}

function handleUserMenuItemClick(item, event) {
  return invokeHeaderItem(item, event, { closeUser: true })
}

function handleMobileDrawerItemClick(item, event) {
  return invokeHeaderItem(item, event, { closeDrawer: true })
}

function startDiscussionFromHeader() {
  startDiscussion({
    source: `header:${String(route.name || 'unknown')}`
  })
}

</script>

<style scoped>
.header {
  background: var(--forum-bg-elevated);
  border-bottom: 1px solid var(--forum-border-color);
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
  color: var(--forum-text-muted);
  font-size: 14px;
  border-radius: 3px;
  transition: all 0.2s;
}

.nav-item i {
  font-size: 14px;
}

.nav-item:hover {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
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

.header-plugin-action {
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--forum-border-color);
  border-radius: 3px;
  background: var(--forum-bg-elevated);
  color: var(--forum-text-muted);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.header-plugin-action:hover {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  text-decoration: none;
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
  background: linear-gradient(90deg, var(--forum-bg-subtle) 0%, var(--forum-border-soft) 50%, var(--forum-bg-subtle) 100%);
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
  color: var(--forum-text-muted);
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
  color: var(--forum-text-muted);
  background: transparent;
}

.btn-login:hover {
  background: var(--forum-bg-subtle);
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
    color: var(--forum-accent-color);
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
  .header-extension-dropdown,
  .header-plugin-action,
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
    background: var(--forum-bg-subtle);
  }
}
</style>
