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
      <Header v-if="showGlobalNavigation" />
      <div v-if="showAnnouncement && showGlobalNavigation" class="site-announcement" :class="`site-announcement--${announcementTone}`">
        <div class="site-announcement-inner">
          <i :class="announcementIcon"></i>
          <p>{{ announcementMessage }}</p>
          <button type="button" aria-label="关闭公告" @click="dismissAnnouncement">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
      <main class="main-content">
        <div v-if="forumRealtimeStatus.shouldShow.value" class="global-runtime-banner">
          <div class="container">
            <ForumInlineMessage :tone="forumRealtimeStatus.tone.value">
              {{ forumRealtimeStatus.text.value }}
            </ForumInlineMessage>
          </div>
        </div>
        <router-view />
      </main>
      <Footer />
      <AppModalHost />
      <component
        :is="host.component"
        v-for="host in composerHosts"
        :key="host.key"
        v-bind="host.componentProps || {}"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Header from './components/Header.vue'
import Footer from './components/Footer.vue'
import AppModalHost from './components/AppModalHost.vue'
import ForumInlineMessage from './components/forum/ForumInlineMessage.vue'
import { useAuthStore, useOnlineUsersStore, openLoginModal } from '@bias/users'
import { useComposerStore } from './stores/composer'
import { useForumStore } from './stores/forum'
import { useForumUiStore } from './stores/forumUi'
import { useForumRealtimeStore } from '@bias/realtime'
import { useForumRealtimeStatus } from './composables/useForumRealtimeStatus'
import { getComposerHosts, getUiCopy, runForumRuntimeHook } from './forum/registry'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const forumUiStore = useForumUiStore()
const forumRealtimeStore = useForumRealtimeStore()
const onlineUsersStore = useOnlineUsersStore()
const route = useRoute()
const forumRealtimeStatus = useForumRealtimeStatus({
  forumRealtimeStore,
  authStore,
  getText: getUiCopy,
})
const dismissedAnnouncementKey = ref('')
const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
const showMaintenance = computed(() => (
  String(forumStore.settings.maintenance_mode_key || (forumStore.settings.maintenance_mode ? 'high' : 'none')) !== 'none'
  && !authStore.user?.is_staff
))
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
const showGlobalNavigation = computed(() => !(
  viewportWidth.value <= 768
  && route.name === 'discussion-detail'
  && composerStore.isOpen
  && !composerStore.isMinimized
  && ['reply', 'edit'].includes(composerStore.current.type)
))
const showAnnouncement = computed(() => (
  Boolean(forumStore.settings.announcement_enabled)
  && Boolean(announcementMessage.value)
  && dismissedAnnouncementKey.value !== announcementKey.value
))
const composerHosts = computed(() => getComposerHosts(buildForumRuntimeContext()))

function syncViewportWidth() {
  if (typeof window === 'undefined') return
  viewportWidth.value = window.innerWidth
}

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

function buildForumRuntimeContext() {
  return {
    authStore,
    forumStore,
    forumUiStore,
    forumRealtimeStore,
    onlineUsersStore,
    route,
  }
}

async function runForumRuntime(name) {
  await runForumRuntimeHook(name, buildForumRuntimeContext())
}

async function syncAuthenticatedRuntime() {
  await runForumRuntime('onAuthenticated')
  forumRealtimeStore.connect({ authStore })
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
  await forumUiStore.initialize()
  applyRouteMeta()
  loadDismissedAnnouncementKey()
  syncViewportWidth()

  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('resize', syncViewportWidth)
  window.addEventListener('bias:auth-required', handleAuthRequired)
  window.addEventListener('bias:auth-invalidated', handleAuthInvalidated)

  // 初始化认证状态
  await authStore.checkAuth()

  onlineUsersStore.connect()

  if (showMaintenance.value) {
    await runForumRuntime('onMaintenance')
    return
  }

  await runForumRuntime('onMounted')

  if (authStore.isAuthenticated) {
    await syncAuthenticatedRuntime()
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
  () => authStore.isAuthenticated,
  async isAuthenticated => {
    if (isAuthenticated) {
      await forumUiStore.refreshFromUserPreferences()
    } else {
      forumUiStore.syncFromForumSettings()
    }

    if (showMaintenance.value) {
      await runForumRuntime('onMaintenance')
      forumRealtimeStore.disconnect()
      onlineUsersStore.disconnect()
      return
    }

    if (isAuthenticated) {
      onlineUsersStore.reconnect()
      await syncAuthenticatedRuntime()
      return
    }

    await runForumRuntime('onGuest')
    forumRealtimeStore.disconnect()
    onlineUsersStore.reconnect()
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
  const routeDocument = resolveRouteDocumentMeta(route)
  if (route.meta?.title || route.meta?.description || routeDocument) {
    forumStore.setPageMeta({
      title: route.meta.title,
      description: route.meta.description,
      ...(routeDocument || {}),
    })
    return
  }

  forumStore.resetPageMeta()
}

function resolveRouteDocumentMeta(currentRoute) {
  const documentMeta = currentRoute.meta?.extensionDocument
  if (!documentMeta || typeof documentMeta !== 'object') {
    return null
  }

  return {
    preloads: resolveRouteDocumentValues(documentMeta.preloads || [], currentRoute),
    documentAttributes: resolveRouteDocumentValues(documentMeta.documentAttributes || [], currentRoute),
    headTags: resolveRouteDocumentValues(documentMeta.headTags || [], currentRoute),
  }
}

function resolveRouteDocumentValues(values, currentRoute) {
  return (Array.isArray(values) ? values : [])
    .map(value => resolveRouteDocumentValue(value, currentRoute))
    .filter(Boolean)
}

function resolveRouteDocumentValue(value, currentRoute) {
  if (typeof value === 'string') {
    return applyRouteParams(value, currentRoute)
  }
  if (Array.isArray(value)) {
    return value.map(item => resolveRouteDocumentValue(item, currentRoute)).filter(Boolean)
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, item]) => [key, resolveRouteDocumentValue(item, currentRoute)])
        .filter(([, item]) => item !== undefined && item !== null && item !== false)
    )
  }
  return value
}

function applyRouteParams(value, currentRoute) {
  return String(value || '').replace(/:([A-Za-z0-9_]+)/g, (_match, key) => {
    const param = currentRoute.params?.[key]
    return encodeURIComponent(Array.isArray(param) ? (param[0] || '') : (param || ''))
  })
}

onBeforeUnmount(() => {
  runForumRuntime('onBeforeUnmount')
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('resize', syncViewportWidth)
  window.removeEventListener('bias:auth-required', handleAuthRequired)
  window.removeEventListener('bias:auth-invalidated', handleAuthInvalidated)
  onlineUsersStore.disconnect()
  forumUiStore.reset()
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

.global-runtime-banner {
  padding-top: 16px;
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
