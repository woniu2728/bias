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
import { useAuthStore } from '../stores/auth'
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

  await adminRegistryStore.fetchModules()

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
}

.Admin-content .container {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--forum-space-7) var(--forum-space-5);
  display: flex;
  align-items: flex-start;
  gap: var(--forum-space-7);
}

.Admin-main {
  flex: 1;
  min-width: 0;
}

@media (max-width: 960px) {
  .Admin-content .container {
    flex-direction: column;
    align-items: stretch;
    gap: 18px;
    padding: 18px 14px 28px;
  }

  .Admin-main {
    width: 100%;
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
