<template>
  <div class="index-page">
    <div class="index-container">
      <DiscussionListSidebar
        :auth-store="authStore"
        :current-tag="currentTag"
        :is-all-discussions-page="isAllDiscussionsPage"
        :is-following-page="isFollowingPage"
        :is-own-profile-page="isOwnProfilePage"
        :is-tags-page="isTagsPage"
        :has-sidebar-tag-navigation="hasSidebarTagNavigation"
        :sidebar-primary-tag-items="sidebarPrimaryTagItems"
        :sidebar-secondary-tag-items="sidebarSecondaryTagItems"
        :show-more-tags-link="showMoreTagsLink"
        :start-discussion-button-style="startDiscussionButtonStyle"
        :build-user-path="buildUserPath"
        :build-tag-path="buildTagPath"
        :is-sidebar-tag-active="isSidebarTagActive"
        :get-sidebar-tag-style="getSidebarTagStyle"
        @start-discussion="handleStartDiscussion"
      />

      <DiscussionListContent
        :auth-store="authStore"
        :current-tag="currentTag"
        :is-following-page="isFollowingPage"
        :sort-by="sortBy"
        :sort-options="sortOptions"
        :marking-all-read="markingAllRead"
        :loading="loading"
        :refreshing="refreshing"
        :discussions="discussions"
        :empty-state-text="emptyStateText"
        :has-more="hasMore"
        :loading-more="loadingMore"
        :build-discussion-path="buildDiscussionPath"
        :build-tag-path="buildTagPath"
        :build-user-path="buildUserPath"
        :format-relative-time="formatRelativeTime"
        :get-user-avatar-color="getUserAvatarColor"
        :get-user-display-name="getUserDisplayName"
        :get-user-initial="getUserInitial"
        @change-sort="changeSortBy"
        @mark-all-read="markAllAsRead"
        @refresh="refreshDiscussionList"
        @load-more="loadMore"
      />
    </div>
  </div>
</template>

<script setup>
import DiscussionListContent from '@/components/discussion/DiscussionListContent.vue'
import DiscussionListSidebar from '@/components/discussion/DiscussionListSidebar.vue'
import { useDiscussionListPage } from '@/composables/useDiscussionListPage'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useModalStore } from '@/stores/modal'
import { useRoute, useRouter } from 'vue-router'
import {
  buildDiscussionPath,
  buildTagPath,
  buildUserPath,
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial
} from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()
const route = useRoute()
const router = useRouter()
const {
  discussions,
  currentTag,
  loading,
  refreshing,
  loadingMore,
  sortBy,
  sortOptions,
  markingAllRead,
  hasMore,
  isFollowingPage,
  isTagsPage,
  isAllDiscussionsPage,
  isOwnProfilePage,
  sidebarPrimaryTagItems,
  sidebarSecondaryTagItems,
  hasSidebarTagNavigation,
  showMoreTagsLink,
  startDiscussionButtonStyle,
  emptyStateText,
  refreshPageData,
  refreshDiscussionList,
  changeSortBy,
  loadMore,
  markAllAsRead,
  handleStartDiscussion,
  getSidebarTagStyle,
  isSidebarTagActive
} = useDiscussionListPage({
  authStore,
  composerStore,
  modalStore,
  route,
  router
})

</script>

<style scoped>
.index-page {
  background: var(--forum-bg-canvas);
  min-height: calc(100vh - 56px);
}

.index-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  gap: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .index-page {
    min-height: calc(100vh - 56px);
  }

  .index-container {
    display: block;
  }
}
</style>
