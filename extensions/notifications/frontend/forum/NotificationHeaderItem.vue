<template>
  <HeaderNotificationsMenu
    :show-notifications="showNotifications"
    :notification-store="notificationStore"
    :notification-items="notificationItems"
    :notification-groups="notificationGroups"
    :notification-type-summaries="notificationTypeSummaries"
    :empty-state-text="emptyStateText"
    :loading-state-text="loadingStateText"
    :has-read-notifications="hasReadNotifications"
    :action-message="actionMessage"
    :action-tone="actionTone"
    :marking-all-read="markingAllRead"
    :clearing-read="clearingRead"
    :get-notification-presentation="getNotificationPresentation"
    :get-notification-icon-class="getNotificationIconClass"
    :get-notification-text-html="getNotificationTextHtml"
    :format-relative-time="formatRelativeTime"
    @toggle="toggleNotifications"
    @mark-all-read="markAllNotificationsAsRead"
    @clear-read="clearReadNotifications"
    @open-group="openNotificationGroup"
    @open-type="openNotificationsPageByType"
    @notification-click="handleNotificationClick"
    @open-page="openNotificationsPage"
  />
</template>

<script setup>
import HeaderNotificationsMenu from './HeaderNotificationsMenu.vue'
import {
  formatRelativeTime,
} from '@bias/forum'
import {
  getNotificationIconClass,
  getNotificationTextHtml,
} from './notificationRuntime.js'
import {
  useForumStore,
  useModalStore,
  useAuthStore,
  useRoute,
  useRouter,
} from '@bias/forum'
import { onBeforeUnmount, onMounted, watch } from '@bias/forum'
import { useHeaderNotifications } from './useHeaderNotifications.js'
import { useNotificationStore } from './store.js'

const authStore = useAuthStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()
const route = useRoute()
const router = useRouter()
const {
  showNotifications,
  notificationItems,
  hasReadNotifications,
  notificationGroups,
  notificationTypeSummaries,
  emptyStateText,
  loadingStateText,
  actionMessage,
  actionTone,
  markingAllRead,
  clearingRead,
  getNotificationPresentation,
  toggleNotifications,
  markAllNotificationsAsRead,
  clearReadNotifications,
  handleNotificationClick,
  openNotificationGroup,
  openNotificationsPage,
  openNotificationsPageByType,
  closeNotifications,
} = useHeaderNotifications({
  modalStore,
  notificationStore,
  forumTitle: forumStore.settings?.forum_title || '论坛',
  router,
})

function handleWindowClick(event) {
  if (!event.target.closest('.notifications-dropdown')) {
    closeNotifications()
  }
}

function handleHeaderOverlayClose() {
  closeNotifications()
}

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (!isAuthenticated) {
      closeNotifications()
    }
  },
  { immediate: true }
)

watch(
  () => route.fullPath,
  () => {
    closeNotifications()
  }
)

onMounted(() => {
  if (typeof window === 'undefined') return
  window.addEventListener('click', handleWindowClick)
  window.addEventListener('bias:header-overlays-close', handleHeaderOverlayClose)
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('click', handleWindowClick)
  window.removeEventListener('bias:header-overlays-close', handleHeaderOverlayClose)
})
</script>
