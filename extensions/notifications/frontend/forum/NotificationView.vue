<template>
  <div class="notification-page">
    <ForumPageWithSidebar>
      <template #sidebar>
        <DiscussionListSidebarStartButton
          v-if="sidebarBindings.showStartDiscussionButton"
          :current-tag="null"
          :start-discussion-button-style="{}"
          @click="sidebarEvents.startDiscussion"
        />

        <ForumPrimaryNav
          :auth-store="sidebarBindings.authStore"
          :notification-store="sidebarBindings.notificationStore"
          active-key="notifications"
        />
      </template>

      <main class="notification-content">
        <ForumHeroPanel
          :title="heroBindings.title"
          :pill="heroBindings.pill"
          :description="heroBindings.description"
          :variant="heroBindings.variant"
        >
          <template #meta>
            <div class="hero-meta">
              <button
                v-if="heroBindings.filteredUnreadCount > 0"
                type="button"
                class="secondary"
                :disabled="heroBindings.marking"
                @click="heroEvents.markAllAsRead"
              >
                {{ heroBindings.markAllButtonText }}
              </button>
              <button
                v-if="heroBindings.filteredReadCount > 0"
                type="button"
                class="secondary"
                :disabled="heroBindings.marking"
                @click="heroEvents.clearReadNotifications"
              >
                {{ heroBindings.clearReadButtonText }}
              </button>
              <button
                type="button"
                class="secondary"
                @click="heroEvents.toggleUnreadOnly"
              >
                {{ heroBindings.unreadToggleText }}
              </button>
              <router-link to="/profile" class="preferences-link">
                {{ heroBindings.preferencesLinkText }}
              </router-link>
            </div>
          </template>
        </ForumHeroPanel>

        <ForumInlineMessage v-if="listBindings.loadError" tone="danger">
          {{ listBindings.loadError }}
        </ForumInlineMessage>

        <section class="notification-filters-card">
          <div class="notification-filters-header">
            <div>
              <h2>{{ filterCardBindings.activeNotificationLabel }}</h2>
              <p>{{ filterCardBindings.filterDescriptionText }}</p>
            </div>
            <div class="notification-view-toggle">
              <button
                v-for="item in filterCardBindings.viewModeItems"
                :key="item.value"
                type="button"
                class="notification-view-toggle-button"
                :class="{ 'is-active': filterCardBindings.viewMode === item.value }"
                @click="filterCardEvents.changeViewMode(item.value)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <ForumSearchFilterNav
            :items="filterCardBindings.notificationTypeItems"
            :active-value="filterCardBindings.activeType"
            @change="filterCardEvents.changeType"
          />
        </section>

        <ForumStateBlock v-if="listBindings.loading" class="notification-state">
          {{ listBindings.loadingStateText }}
        </ForumStateBlock>

        <ForumStateBlock v-else-if="listBindings.notifications.length === 0" class="notification-state">
          {{ listBindings.emptyStateText }}
        </ForumStateBlock>

        <NotificationList
          v-else-if="listBindings.viewMode === 'timeline'"
          :notifications="listBindings.notifications"
          :format-date="listBindings.formatDate"
          :get-avatar-color="listBindings.getNotificationAvatarColor"
          :get-avatar-initial="listBindings.getNotificationAvatarInitial"
          :get-display-name="listBindings.getUserDisplayName"
          :get-icon-class="listBindings.getNotificationIconClass"
          :get-message-html="listBindings.getNotificationMessageHtml"
          :get-presentation="listBindings.getNotificationPresentation"
          @click="listEvents.handleNotificationClick"
          @mark-read="listEvents.markAsRead"
          @delete="listEvents.deleteNotification"
        />

        <div v-else class="notification-group-stack">
          <section
            v-for="group in listBindings.groupedNotifications"
            :key="group.key"
            class="notification-group-panel"
          >
            <header class="notification-group-panel-header">
              <div>
                <h3>{{ group.title }}</h3>
                <p>{{ listBindings.groupCountText(group.items.length) }}</p>
              </div>
              <button
                v-if="group.discussionId"
                type="button"
                class="secondary"
                @click="listEvents.openDiscussion(group.discussionId)"
              >
                {{ listBindings.openDiscussionText }}
              </button>
            </header>

            <div v-if="group.discussionId" class="notification-group-panel-actions">
              <button
                v-if="group.items.some(item => !item.is_read)"
                type="button"
                class="secondary"
                :disabled="listBindings.marking"
                @click="listEvents.markGroupAsRead(group)"
              >
                {{ listBindings.markGroupReadText }}
              </button>
              <button
                v-if="group.items.some(item => item.is_read)"
                type="button"
                class="secondary danger"
                :disabled="listBindings.marking"
                @click="listEvents.clearGroupReadNotifications(group)"
              >
                {{ listBindings.clearGroupReadText }}
              </button>
            </div>

            <NotificationList
              :notifications="group.items"
              :format-date="listBindings.formatDate"
              :get-avatar-color="listBindings.getNotificationAvatarColor"
              :get-avatar-initial="listBindings.getNotificationAvatarInitial"
              :get-display-name="listBindings.getUserDisplayName"
              :get-icon-class="listBindings.getNotificationIconClass"
              :get-message-html="listBindings.getNotificationMessageHtml"
              :get-presentation="listBindings.getNotificationPresentation"
              @click="listEvents.handleNotificationClick"
              @mark-read="listEvents.markAsRead"
              @delete="listEvents.deleteNotification"
            />
          </section>
        </div>

        <ForumPagination
          v-if="listBindings.totalPages > 1"
          :current-page="listBindings.currentPage"
          :total-pages="listBindings.totalPages"
          @change="listEvents.changePage"
        />
      </main>
    </ForumPageWithSidebar>
  </div>
</template>

<script setup>
import {
  DiscussionListSidebarStartButton,
  ForumHeroPanel,
  ForumInlineMessage,
  ForumPageWithSidebar,
  ForumPagination,
  ForumPrimaryNav,
  ForumSearchFilterNav,
  ForumStateBlock,
  useAuthStore,
  useComposerStore,
  useForumStore,
  useModalStore,
  useRoute,
  useRouter,
} from '@bias/forum'
import NotificationList from './NotificationList.vue'
import { useNotificationViewModel } from './useNotificationViewModel.js'
import { useNotificationStore } from './store.js'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()
const {
  filterCardBindings,
  filterCardEvents,
  heroBindings,
  heroEvents,
  listBindings,
  listEvents,
  sidebarBindings,
  sidebarEvents,
} = useNotificationViewModel({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  notificationStore,
  route,
  router
})
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

.notification-group-panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.secondary.danger {
  color: #a44d47;
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
