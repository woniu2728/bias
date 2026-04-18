<template>
  <div id="app">
    <template v-if="showMaintenance">
      <main class="maintenance-shell">
        <section class="maintenance-card">
          <p class="maintenance-eyebrow">Maintenance Mode</p>
          <h1>论坛暂时不可用</h1>
          <p>{{ forumStore.settings.maintenance_message }}</p>
        </section>
      </main>
    </template>
    <template v-else>
      <Header />
      <main class="main-content">
        <router-view />
      </main>
      <Footer />
      <AppModalHost />
      <DiscussionComposer />
      <PostComposer />
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Header from './components/Header.vue'
import Footer from './components/Footer.vue'
import AppModalHost from './components/AppModalHost.vue'
import DiscussionComposer from './components/DiscussionComposer.vue'
import PostComposer from './components/PostComposer.vue'
import { useAuthStore } from './stores/auth'
import { useComposerStore } from './stores/composer'
import { useForumStore } from './stores/forum'
import { useNotificationStore } from './stores/notification'
import { openLoginModal } from './utils/authModal'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const notificationStore = useNotificationStore()
const route = useRoute()
const showMaintenance = computed(() => forumStore.settings.maintenance_mode && !authStore.user?.is_staff)

function handleBeforeUnload(event) {
  if (!composerStore.hasUnsavedChanges) return
  event.preventDefault()
  event.returnValue = composerStore.unsavedMessage || ''
}

async function syncNotificationState() {
  try {
    await notificationStore.fetchStats()
  } catch (error) {
    console.error('同步通知角标失败:', error)
  }

  notificationStore.connect()
}

function handleAuthRequired(event) {
  authStore.logout()

  const redirect = event?.detail?.redirect || route.fullPath
  openLoginModal({ redirectPath: redirect })
}

onMounted(async () => {
  await forumStore.initialize()

  // 初始化认证状态
  await authStore.checkAuth()

  if (showMaintenance.value) {
    window.addEventListener('beforeunload', handleBeforeUnload)
    return
  }

  // 如果已登录，连接WebSocket
  if (authStore.isAuthenticated) {
    await syncNotificationState()
  }

  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('bias:auth-required', handleAuthRequired)
})

watch(
  () => authStore.isAuthenticated,
  async isAuthenticated => {
    if (showMaintenance.value) {
      notificationStore.disconnect()
      notificationStore.resetState()
      return
    }

    if (isAuthenticated) {
      await syncNotificationState()
      return
    }

    notificationStore.disconnect()
    notificationStore.resetState()
  }
)

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('bias:auth-required', handleAuthRequired)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f8fa;
  color: #333;
  font-size: 14px;
  line-height: 1.6;
}

:root {
  --forum-primary-color: #4d698e;
  --forum-accent-color: #e74c3c;
  --composer-offset: 0px;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.maintenance-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  background:
    radial-gradient(circle at top, rgba(77, 105, 142, 0.18), transparent 48%),
    linear-gradient(180deg, #f6f8fb 0%, #eef2f7 100%);
}

.maintenance-card {
  width: min(560px, 100%);
  padding: 36px 32px;
  border: 1px solid rgba(77, 105, 142, 0.16);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 60px rgba(45, 62, 80, 0.12);
}

.maintenance-card h1 {
  margin-bottom: 14px;
  font-size: 32px;
  color: #223041;
}

.maintenance-card p {
  color: #4f5f70;
  font-size: 15px;
}

.maintenance-eyebrow {
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 12px;
  font-weight: 700;
  color: #4d698e;
}

.main-content {
  flex: 1;
  padding-bottom: var(--composer-offset);
  transition: padding-bottom 0.15s ease;
}

a {
  color: var(--forum-primary-color);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

button {
  cursor: pointer;
  border: none;
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  font-family: inherit;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.primary {
  background: var(--forum-primary-color);
  color: white;
}

button.primary:hover:not(:disabled) {
  filter: brightness(0.92);
}

button.secondary {
  background: #e3e8ed;
  color: #555;
}

button.secondary:hover:not(:disabled) {
  background: #d3d8dd;
}

button.danger {
  background: #e74c3c;
  color: white;
}

button.danger:hover:not(:disabled) {
  background: #c0392b;
}

button.full-width {
  width: 100%;
}

input, textarea, select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 13px;
  font-family: inherit;
}

input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--forum-primary-color);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}
</style>
