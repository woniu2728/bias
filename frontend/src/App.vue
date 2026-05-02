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
      <div v-if="showAnnouncement" class="site-announcement" :class="`site-announcement--${announcementTone}`">
        <div class="site-announcement-inner">
          <i :class="announcementIcon"></i>
          <p>{{ announcementMessage }}</p>
          <button type="button" aria-label="关闭公告" @click="dismissAnnouncement">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
const dismissedAnnouncementKey = ref('')
const showMaintenance = computed(() => forumStore.settings.maintenance_mode && !authStore.user?.is_staff)
const announcementMessage = computed(() => String(forumStore.settings.announcement_message || '').trim())
const announcementTone = computed(() => {
  const tone = String(forumStore.settings.announcement_tone || 'info')
  return ['info', 'warning', 'success'].includes(tone) ? tone : 'info'
})
const announcementIcon = computed(() => {
  if (announcementTone.value === 'warning') return 'fas fa-exclamation-triangle'
  if (announcementTone.value === 'success') return 'fas fa-check-circle'
  return 'fas fa-bullhorn'
})
const announcementKey = computed(() => {
  if (!announcementMessage.value) return ''
  return `${announcementTone.value}:${announcementMessage.value}`
})
const showAnnouncement = computed(() => (
  Boolean(forumStore.settings.announcement_enabled)
  && Boolean(announcementMessage.value)
  && dismissedAnnouncementKey.value !== announcementKey.value
))

function loadDismissedAnnouncementKey() {
  if (typeof window === 'undefined') return
  dismissedAnnouncementKey.value = window.localStorage.getItem('bias.dismissedAnnouncement') || ''
}

function dismissAnnouncement() {
  dismissedAnnouncementKey.value = announcementKey.value
  if (typeof window !== 'undefined') {
    window.localStorage.setItem('bias.dismissedAnnouncement', announcementKey.value)
  }
}

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

function handleAuthInvalidated() {
  authStore.logout()
}

onMounted(async () => {
  await forumStore.initialize()
  applyRouteMeta()
  loadDismissedAnnouncementKey()

  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('bias:auth-required', handleAuthRequired)
  window.addEventListener('bias:auth-invalidated', handleAuthInvalidated)

  // 初始化认证状态
  await authStore.checkAuth()

  if (showMaintenance.value) {
    return
  }

  // 如果已登录，连接WebSocket
  if (authStore.isAuthenticated) {
    await syncNotificationState()
  }
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

watch(
  () => route.fullPath,
  () => {
    applyRouteMeta()
  },
  { immediate: true }
)

function applyRouteMeta() {
  if (route.meta?.title || route.meta?.description) {
    forumStore.setPageMeta({
      title: route.meta.title,
      description: route.meta.description,
    })
    return
  }

  forumStore.resetPageMeta()
}

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('bias:auth-required', handleAuthRequired)
  window.removeEventListener('bias:auth-invalidated', handleAuthInvalidated)
})
</script>

<style>
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
  border-radius: var(--forum-radius-lg);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--forum-shadow-lg);
}

.maintenance-card h1 {
  margin-bottom: 14px;
  font-size: var(--forum-font-size-3xl);
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

.site-announcement {
  border-bottom: 1px solid var(--forum-border-color);
  background: var(--forum-info-bg);
  color: var(--forum-text-color);
}

.site-announcement--warning {
  background: var(--forum-warning-bg);
  border-bottom-color: var(--forum-warning-border);
}

.site-announcement--success {
  background: #edf8f2;
  border-bottom-color: #c9ead8;
}

.site-announcement-inner {
  max-width: 1200px;
  min-height: 42px;
  margin: 0 auto;
  padding: 8px 20px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.site-announcement i {
  color: var(--forum-primary-color);
}

.site-announcement--warning i {
  color: var(--forum-warning-color);
}

.site-announcement--success i {
  color: var(--forum-success-color);
}

.site-announcement p {
  min-width: 0;
  color: inherit;
  font-size: var(--forum-font-size-sm);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.site-announcement button {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background: transparent;
  color: var(--forum-text-muted);
}

.site-announcement button:hover {
  border-color: var(--forum-border-color);
  background: rgba(255, 255, 255, 0.55);
}

@media (max-width: 768px) {
  .site-announcement-inner {
    padding: 8px 14px;
    gap: 8px;
  }
}
</style>
