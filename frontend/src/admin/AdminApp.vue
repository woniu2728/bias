<template>
  <div id="admin-app">
    <AdminHeader :mobile-nav-open="showMobileNav" @toggle-nav="toggleMobileNav" @close-nav="closeMobileNav" />
    <div class="Admin-content">
      <div class="container">
        <AdminNav :mobile-open="showMobileNav" @close="closeMobileNav" />
        <div class="Admin-main">
          <router-view />
        </div>
      </div>
    </div>
    <AppModalHost />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppModalHost from '../components/AppModalHost.vue'
import AdminHeader from './components/AdminHeader.vue'
import AdminNav from './components/AdminNav.vue'
import { useAuthStore } from '@bias/users'
import { useAdminRegistryStore } from '../stores/adminRegistry'
import { useForumStore } from '../stores/forum'
import { useForumUiStore } from '../stores/forumUi'
import { useModalStore } from '../stores/modal'
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const adminRegistryStore = useAdminRegistryStore()
const forumStore = useForumStore()
const forumUiStore = useForumUiStore()
const modalStore = useModalStore()
const router = useRouter()
const route = useRoute()
const showMobileNav = ref(false)

function toggleMobileNav() {
  showMobileNav.value = !showMobileNav.value
}

function closeMobileNav() {
  showMobileNav.value = false
}

function handleAuthInvalidated() {
  authStore.logout()
  closeMobileNav()
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('bias:auth-invalidated', handleAuthInvalidated)
  }

  await forumUiStore.initialize()

  // 检查认证状态
  await authStore.checkAuth()
  await forumUiStore.refreshFromUserPreferences()

  // 检查是否是管理员
  if (!authStore.user?.is_staff) {
    await modalStore.alert({
      title: '无法访问后台',
      message: '需要管理员权限',
      tone: 'danger'
    })
    router.replace('/')
    return
  }

  await adminRegistryStore.fetchExtensions()

  // 如果当前路径不是 /admin 开头，重定向到仪表盘
  if (!route.path.startsWith('/admin')) {
    router.replace('/admin')
  }
})

watch(
  () => forumStore.settings,
  () => {
    forumUiStore.syncFromForumSettings()
  },
  { deep: true }
)

watch(
  () => route.fullPath,
  () => {
    closeMobileNav()
  }
)

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('bias:auth-invalidated', handleAuthInvalidated)
  }
  forumUiStore.reset()
})
</script>

<style>
#admin-app {
  min-height: 100vh;
  background: var(--forum-bg-canvas);
}

.Admin-content {
  padding-top: 56px;
  height: 100vh;
  overflow: hidden;
}

.Admin-content .container {
  max-width: none;
  margin: 0;
  padding: 20px 30px 0;
  display: flex;
  align-items: flex-start;
  gap: 30px;
  height: calc(100vh - 56px);
  overflow: hidden;
}

.Admin-main {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
  padding-bottom: 28px;
  scrollbar-width: thin;
  scrollbar-color: rgba(128, 142, 158, 0.9) transparent;
}

.Admin-main::-webkit-scrollbar {
  width: 12px;
}

.Admin-main::-webkit-scrollbar-track {
  background: transparent;
}

.Admin-main::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background: rgba(128, 142, 158, 0.85);
  background-clip: padding-box;
}

@media (max-width: 960px) {
  .Admin-content {
    height: auto;
    overflow: visible;
  }

  .Admin-content .container {
    flex-direction: column;
    align-items: stretch;
    gap: 18px;
    padding: 18px 14px 28px;
    height: auto;
    overflow: visible;
  }

  .Admin-main {
    width: 100%;
    height: auto;
    overflow: visible;
    padding-bottom: 0;
  }
}

@media (max-width: 768px) {
  .Admin-content {
    padding-top: 56px;
  }

  .Admin-content .container {
    padding: 0 0 24px;
    gap: 0;
  }
}
</style>
