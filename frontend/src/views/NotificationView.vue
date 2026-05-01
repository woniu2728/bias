<template>
  <div class="notification-page">
    <ForumPageWithSidebar>
      <template #sidebar>
        <DiscussionListSidebarStartButton
          v-if="!authStore.isAuthenticated || authStore.canStartDiscussion"
          :current-tag="null"
          :start-discussion-button-style="{}"
          @click="handleStartDiscussion"
        />

        <ForumPrimaryNav :auth-store="authStore" active-key="notifications" />
      </template>

      <main class="notification-content">
        <ForumHeroPanel
          title="通知"
          pill="消息中心"
          description="这里会显示回复、提及、点赞、审核和账号状态相关通知。"
          variant="primary"
        >
          <template #meta>
            <div class="hero-meta">
              <button
                v-if="notifications.length > 0"
                type="button"
                class="secondary"
                :disabled="marking"
                @click="markAllAsRead"
              >
                {{ marking ? '处理中...' : '全部标记为已读' }}
              </button>
              <router-link to="/profile" class="preferences-link">
                通知偏好前往个人设置
              </router-link>
            </div>
          </template>
        </ForumHeroPanel>

        <ForumInlineMessage v-if="loadError" tone="danger">
          {{ loadError }}
        </ForumInlineMessage>

        <ForumStateBlock v-if="loading" class="notification-state">
          正在加载通知...
        </ForumStateBlock>

        <ForumStateBlock v-else-if="notifications.length === 0" class="notification-state">
          暂无通知
        </ForumStateBlock>

        <ForumNotificationList
          v-else
          :notifications="notifications"
          :format-date="formatDate"
          :get-avatar-color="getNotificationAvatarColor"
          :get-avatar-initial="getNotificationAvatarInitial"
          :get-display-name="getUserDisplayName"
          :get-icon-class="getNotificationIconClass"
          :get-message-html="getNotificationMessageHtml"
          @click="handleNotificationClick"
          @mark-read="markAsRead"
          @delete="deleteNotification"
        />

        <ForumPagination
          v-if="totalPages > 1"
          :current-page="currentPage"
          :total-pages="totalPages"
          @change="changePage"
        />
      </main>
    </ForumPageWithSidebar>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import {
  getNotificationIconClass,
  getNotificationTextHtml
} from '@/composables/useNotificationPresentation'
import ForumHeroPanel from '@/components/forum/ForumHeroPanel.vue'
import ForumInlineMessage from '@/components/forum/ForumInlineMessage.vue'
import ForumNotificationList from '@/components/forum/ForumNotificationList.vue'
import ForumPagination from '@/components/forum/ForumPagination.vue'
import ForumPageWithSidebar from '@/components/forum/ForumPageWithSidebar.vue'
import ForumPrimaryNav from '@/components/forum/ForumPrimaryNav.vue'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import DiscussionListSidebarStartButton from '@/components/discussion/DiscussionListSidebarStartButton.vue'
import { useNotificationPage } from '@/composables/useNotificationPage'
import { useComposerStore } from '@/stores/composer'
import { useAuthStore } from '@/stores/auth'
import { useModalStore } from '@/stores/modal'
import { useNotificationStore } from '@/stores/notification'
import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import {
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial
} from '@/utils/forum'

const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()
const { startDiscussion } = useStartDiscussionAction({
  authStore,
  composerStore,
  router
})
const {
  notifications,
  loading,
  loadError,
  marking,
  currentPage,
  totalPages,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  handleNotificationClick,
  changePage
} = useNotificationPage({
  modalStore,
  notificationStore,
  router
})

function handleStartDiscussion() {
  startDiscussion({
    source: 'notifications'
  })
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}

function getNotificationMessageHtml(notification) {
  return getNotificationTextHtml(notification)
}

function getNotificationAvatarInitial(notification) {
  return getUserInitial(notification.from_user || {})
}

function getNotificationAvatarColor(notification) {
  return getUserAvatarColor(notification.from_user || {})
}
</script>

<style scoped>
.notification-page {
  background: var(--forum-bg-canvas);
  min-height: calc(100vh - 56px);
}

.notification-content {
  padding: 24px 28px 40px;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.preferences-link {
  color: var(--forum-text-muted);
  font-size: 13px;
  font-weight: 500;
}

.preferences-link:hover {
  color: var(--forum-primary-color);
  text-decoration: none;
}

.notification-state {
  margin: 0;
}

@media (max-width: 900px) {
  .notification-content {
    padding: 18px 15px 28px;
  }
}

@media (max-width: 768px) {
  .hero-meta {
    align-items: stretch;
  }
}
</style>
