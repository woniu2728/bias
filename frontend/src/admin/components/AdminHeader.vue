<template>
  <header class="AdminHeader">
    <div class="container">
      <div class="AdminHeader-left">
        <a :href="forumUrl" class="AdminHeader-backButton" aria-label="返回论坛">
          <i class="fas fa-angle-left"></i>
        </a>

        <div class="AdminHeader-logo">
          <router-link to="/admin" class="AdminHeader-logoLink">
            <span class="icon" aria-hidden="true">
              <i class="fas fa-sliders-h"></i>
            </span>
            <span class="text">管理后台</span>
          </router-link>
        </div>
      </div>

      <div class="AdminHeader-mobileTitle">
        {{ activeMeta.label }}
      </div>

      <a :href="forumUrl" class="AdminHeader-mobileBack Button Button--icon" aria-label="返回论坛">
        <i class="fas fa-angle-left"></i>
      </a>

      <div class="AdminHeader-actions">
        <div class="AdminHeader-userMenu" ref="userMenuRef">
          <button
            type="button"
            class="AdminHeader-userTrigger"
            :aria-expanded="showUserMenu"
            aria-label="打开管理员菜单"
            @click="toggleUserMenu"
          >
            <span v-if="authStore.user?.avatar_url" class="AdminHeader-avatar">
              <img :src="authStore.user.avatar_url" :alt="displayName" />
            </span>
            <span
              v-else
              class="AdminHeader-avatar AdminHeader-avatar--fallback"
              :style="userAvatarStyle"
            >
              {{ userInitial }}
            </span>
            <span class="AdminHeader-userName">{{ displayName }}</span>
            <i class="fas fa-angle-down"></i>
          </button>

          <div v-if="showUserMenu" class="AdminHeader-userDropdown">
            <button type="button" class="AdminHeader-userDropdownItem" @click="handleLogout">
              退出登录
            </button>
          </div>
        </div>
      </div>

      <div class="AdminHeader-mobileActions">
        <button
          type="button"
          class="Button Button--icon AdminHeader-mobileMenuButton"
          :aria-expanded="mobileNavOpen"
          aria-label="打开后台菜单"
          @click="$emit('toggle-nav')"
        >
          <i class="fas fa-ellipsis-h"></i>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getUserAvatarColor, getUserInitial } from '@/utils/forum'
import { useAuthStore } from '@bias/users'
import { getAdminRouteMeta } from '../navigation'

defineProps({
  mobileNavOpen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle-nav', 'close-nav'])

const authStore = useAuthStore()
const route = useRoute()
const showUserMenu = ref(false)
const userMenuRef = ref(null)

const forumUrl = computed(() => '/')
const activeMeta = computed(() => getAdminRouteMeta(route.path))
const displayName = computed(() => authStore.user?.display_name || authStore.user?.username || 'admin')
const userInitial = computed(() => getUserInitial(authStore.user))
const userAvatarStyle = computed(() => (
  authStore.user?.avatar_url ? {} : { backgroundColor: getUserAvatarColor(authStore.user) }
))

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

function handleDocumentClick(event) {
  if (!userMenuRef.value?.contains(event.target)) {
    showUserMenu.value = false
  }
}

function handleLogout() {
  showUserMenu.value = false
  authStore.logout()
  window.location.href = '/login'
}

onMounted(() => {
  if (typeof document !== 'undefined') {
    document.addEventListener('click', handleDocumentClick)
  }
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('click', handleDocumentClick)
  }
})
</script>

<style scoped>
.AdminHeader {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: var(--forum-bg-elevated);
  border-bottom: 1px solid var(--forum-border-color);
  box-shadow: var(--forum-shadow-sm);
  z-index: 1000;
  height: 56px;
}

.AdminHeader .container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.AdminHeader-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.AdminHeader-backButton {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid var(--forum-border-color);
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.AdminHeader-backButton:hover {
  background: color-mix(in srgb, var(--forum-primary-color) 8%, var(--forum-bg-subtle));
  border-color: color-mix(in srgb, var(--forum-primary-color) 26%, var(--forum-border-color));
  color: var(--forum-primary-color);
  text-decoration: none;
}

.AdminHeader-logo a {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--forum-font-size-lg);
  font-weight: 600;
  color: var(--forum-primary-color);
  text-decoration: none;
}

.AdminHeader-mobileTitle,
.AdminHeader-mobileActions {
  display: none;
}

.AdminHeader-mobileBack.Button--icon {
  display: none;
}

.AdminHeader-logo .icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--forum-primary-color) 10%, white);
  color: var(--forum-primary-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex: 0 0 auto;
}

.AdminHeader-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.AdminHeader-userMenu {
  position: relative;
}

.AdminHeader-userTrigger {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 6px 12px 6px 8px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--forum-text-muted);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.AdminHeader-userTrigger:hover,
.AdminHeader-userTrigger[aria-expanded='true'] {
  background: var(--forum-bg-subtle);
  border-color: var(--forum-border-color);
}

.AdminHeader-avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  overflow: hidden;
  flex: 0 0 auto;
  background: var(--forum-bg-subtle);
}

.AdminHeader-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.AdminHeader-avatar--fallback {
  align-items: center;
  justify-content: center;
  display: inline-flex;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.AdminHeader-userName {
  max-width: 140px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--forum-text-color);
  font-size: 15px;
}

.AdminHeader-userDropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 140px;
  padding: 8px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-md);
}

.AdminHeader-userDropdownItem {
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--forum-text-color);
  text-align: left;
  cursor: pointer;
}

.AdminHeader-userDropdownItem:hover {
  background: var(--forum-bg-subtle);
}

.Button--link {
  background: var(--forum-bg-subtle);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  color: var(--forum-primary-color);
  min-height: 38px;
  padding: 8px 14px;
  font-size: var(--forum-font-size-sm);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.Button--link:hover {
  background: #e3ebf4;
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-strong);
  text-decoration: none;
}

.Button--icon {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  color: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 768px) {
  .AdminHeader {
    height: 56px;
    min-height: 56px;
    background: var(--forum-primary-color);
    border-bottom: 1px solid rgba(15, 23, 42, 0.14);
    box-shadow: var(--forum-shadow-md);
    color: #fff;
  }

  .AdminHeader .container {
    padding: 0 12px;
    align-items: center;
    flex-direction: row;
    gap: 12px;
    justify-content: center;
  }

  .AdminHeader-logo {
    display: none;
  }

  .AdminHeader-left {
    display: none;
  }

  .AdminHeader-mobileTitle {
    display: block;
    max-width: calc(100vw - 120px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 16px;
    font-weight: 700;
    line-height: 56px;
    text-align: center;
    color: #fff;
    text-shadow: 0 1px 1px rgba(15, 23, 42, 0.16);
  }

  .AdminHeader-mobileBack.Button--icon {
    position: absolute;
    left: 10px;
    top: 8px;
    display: inline-flex;
  }

  .AdminHeader-actions {
    display: none;
  }

  .AdminHeader-mobileActions {
    position: absolute;
    inset: 8px 10px 8px auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .AdminHeader-mobileBack.Button--icon,
  .AdminHeader-mobileMenuButton {
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.22);
    color: #fff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }

  .AdminHeader-mobileBack.Button--icon:hover,
  .AdminHeader-mobileMenuButton:hover {
    background: rgba(255, 255, 255, 0.22);
  }
}

@media (max-width: 480px) {
  .AdminHeader-mobileTitle {
    max-width: calc(100vw - 108px);
  }
}
</style>
