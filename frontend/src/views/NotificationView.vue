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
              <button
                type="button"
                class="secondary"
                @click="toggleUnreadOnly"
              >
                {{ unreadOnly ? '查看全部通知' : '仅看未读' }}
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

        <section class="notification-filters-card">
          <div class="notification-filters-header">
            <div>
              <h2>{{ activeNotificationLabel }}</h2>
              <p>按通知类型筛选消息流，方便集中处理提及、点赞、审核和账号状态通知。</p>
            </div>
            <div class="notification-view-toggle">
              <button
                v-for="item in viewModeItems"
                :key="item.value"
                type="button"
                class="notification-view-toggle-button"
                :class="{ 'is-active': viewMode === item.value }"
                @click="changeViewMode(item.value)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <ForumSearchFilterNav
            :items="notificationTypeItems"
            :active-value="activeType"
            @change="changeType"
          />
        </section>

        <ForumStateBlock v-if="loading" class="notification-state">
          正在加载通知...
        </ForumStateBlock>

        <ForumStateBlock v-else-if="notifications.length === 0" class="notification-state">
          暂无通知
        </ForumStateBlock>

        <ForumNotificationList
          v-else-if="viewMode === 'timeline'"
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

        <div v-else class="notification-group-stack">
          <section
            v-for="group in groupedNotifications"
            :key="group.key"
            class="notification-group-panel"
          >
            <header class="notification-group-panel-header">
              <div>
                <h3>{{ group.title }}</h3>
                <p>{{ group.items.length }} 条通知</p>
              </div>
              <button
                v-if="group.discussionId"
                type="button"
                class="secondary"
                @click="router.push(`/d/${group.discussionId}`)"
              >
                打开讨论
              </button>
            </header>

            <ForumNotificationList
              :notifications="group.items"
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
          </section>
        </div>

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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import ForumSearchFilterNav from '@/components/forum/ForumSearchFilterNav.vue'
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

const route = useRoute()
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
  activeType,
  unreadOnly,
  viewMode,
  notificationTypeItems,
  viewModeItems,
  groupedNotifications,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  handleNotificationClick,
  changeType,
  changeViewMode,
  toggleUnreadOnly,
  changePage
} = useNotificationPage({
  modalStore,
  notificationStore,
  route,
  router
})

const activeNotificationLabel = computed(() => {
  const activeItem = notificationTypeItems.value.find(item => item.value === activeType.value)
  return activeItem?.label || '全部通知'
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

.notification-filters-card {
  margin: 18px 0;
  padding: 18px;
  border: 1px solid #dde6ee;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 252, 0.98));
  box-shadow: 0 14px 36px rgba(20, 36, 54, 0.06);
}

.notification-filters-header {
  margin-bottom: 14px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.notification-filters-header h2 {
  margin: 0;
  font-size: 18px;
  color: #1f2f3d;
}

.notification-filters-header p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6d7d8c;
}

.notification-view-toggle {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: #edf3f8;
}

.notification-view-toggle-button {
  border: 0;
  background: transparent;
  color: #5e7287;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
}

.notification-view-toggle-button.is-active {
  background: #fff;
  color: #23384c;
  box-shadow: 0 6px 16px rgba(41, 57, 75, 0.12);
}

.notification-group-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.notification-group-panel {
  border: 1px solid #dde6ee;
  border-radius: 16px;
  padding: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98));
  box-shadow: 0 12px 30px rgba(20, 36, 54, 0.06);
}

.notification-group-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.notification-group-panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #213243;
}

.notification-group-panel-header p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #758698;
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
  overflow-wrap: anywhere;
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

  .notification-filters-card {
    padding: 16px;
  }
}

@media (max-width: 768px) {
  .hero-meta {
    align-items: stretch;
  }

  .notification-group-panel-header {
    flex-direction: column;
  }
}

@media (max-width: 520px) {
  .notification-content {
    padding: 16px 12px 28px;
  }
}
</style>
