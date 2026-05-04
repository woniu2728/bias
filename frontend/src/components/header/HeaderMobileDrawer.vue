<template>
  <transition name="mobile-drawer-fade">
    <div
      v-if="showMobileDrawer"
      class="mobile-drawer-backdrop"
      @click="$emit('close')"
    ></div>
  </transition>

  <aside class="mobile-drawer" :class="{ 'is-open': showMobileDrawer }">
    <div class="mobile-drawer-header">
      <router-link
        to="/"
        class="mobile-drawer-brand"
        @click="$emit('close')"
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
        @click="$emit('close')"
      >
        <i class="fas fa-times"></i>
      </button>
    </div>

    <div class="mobile-drawer-section">
      <button type="button" class="mobile-drawer-search" @click="$emit('open-search')">
        <i class="fas fa-search"></i>
        <span>{{ currentSearchQuery ? `搜索：${currentSearchQuery}` : '搜索论坛' }}</span>
      </button>

      <button
        v-if="authStore.canStartDiscussion"
        type="button"
        class="mobile-drawer-compose"
        @click="$emit('start-discussion')"
      >
        <i class="fas fa-pen-to-square"></i>
        <span>发起讨论</span>
      </button>
    </div>

    <nav class="mobile-drawer-nav">
      <router-link
        v-for="item in navItems"
        :key="item.key"
        :to="item.to"
        class="mobile-drawer-link"
        :class="{ active: isMobileNavActive(item.key) }"
        @click="$emit('close')"
      >
        <i :class="item.icon"></i>
        <span>{{ item.label }}</span>
        <span v-if="item.key === 'notifications' && notificationStore.unreadCount > 0" class="mobile-drawer-badge">
          {{ notificationStore.unreadCount }}
        </span>
      </router-link>
    </nav>

    <div v-if="authStore.isAuthenticated && authStore.user" class="mobile-drawer-user">
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
      <button type="button" class="mobile-drawer-link mobile-drawer-link--danger" @click="$emit('logout')">
        <i class="fas fa-sign-out-alt"></i>
        <span>登出</span>
      </button>
    </div>

    <div v-else class="mobile-drawer-auth">
      <button type="button" class="btn-login" @click="$emit('open-login')">登录</button>
      <button type="button" class="btn-signup" @click="$emit('open-register')">注册</button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { getForumNavItems } from '@/forum/registry'

const props = defineProps({
  showMobileDrawer: {
    type: Boolean,
    default: false
  },
  authStore: {
    type: Object,
    required: true
  },
  forumStore: {
    type: Object,
    required: true
  },
  notificationStore: {
    type: Object,
    required: true
  },
  currentSearchQuery: {
    type: String,
    default: ''
  },
  isMobileNavActive: {
    type: Function,
    required: true
  },
  profilePath: {
    type: Function,
    required: true
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserInitial: {
    type: Function,
    required: true
  }
})

defineEmits([
  'close',
  'open-search',
  'start-discussion',
  'logout',
  'open-login',
  'open-register'
])

const navItems = computed(() => getForumNavItems({
  authStore: props.authStore,
  showNotifications: props.authStore.isAuthenticated && Boolean(props.authStore.user),
}))
</script>

<style scoped>
.mobile-drawer,
.mobile-drawer-backdrop {
  display: none;
}

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

@media (max-width: 900px) {
  .mobile-drawer,
  .mobile-drawer-backdrop {
    display: block;
  }

  .mobile-drawer-close:hover {
    background: #f4f7fa;
  }
}
</style>
