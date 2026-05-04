<template>
  <div class="discussion-detail-page">
    <div class="container">
      <ForumStateBlock v-if="loading" class="discussion-state-block">加载中...</ForumStateBlock>
      <ForumStateBlock v-else-if="!discussion" class="discussion-state-block">讨论不存在</ForumStateBlock>
      <div v-else class="layout">
        <!-- 主内容区 -->
        <main class="main-content">
          <DiscussionHero
            :discussion="discussion"
            :discussion-header-style="discussionHeaderStyle"
            :can-moderate-pending-discussion="canModeratePendingDiscussion"
            :can-edit-discussion="canEditDiscussion"
            :build-tag-path="buildTagPath"
            @moderate-discussion="moderateDiscussion"
            @edit-discussion="editDiscussion"
          />

          <DiscussionMobileActions
            ref="discussionMobileNavRef"
            :discussion="discussion"
            :auth-store="authStore"
            :is-suspended="isSuspended"
            :show-discussion-menu="showDiscussionMenu"
            :can-reply-from-menu="canReplyFromMenu"
            :has-active-composer="hasActiveComposer"
            :toggling-subscription="togglingSubscription"
            :can-edit-discussion="canEditDiscussion"
            :can-moderate-discussion-settings="canModerateDiscussionSettings"
            :menu-items="discussionMenuItems"
            @menu-action="handleDiscussionMenuSelection"
          />

          <div v-if="hasPrevious" ref="previousTrigger" class="load-more load-previous">
            <ForumLoadMoreButton
              compact
              :loading="loadingPrevious"
              text="加载前面的回复"
              loading-text="正在加载回复..."
              @click="loadPreviousPosts"
            />
          </div>

          <!-- 帖子列表 -->
          <div class="posts">
            <template v-for="post in posts" :key="post.id">
              <div
                v-if="showUnreadDivider(post)"
                class="post-unread-divider"
              >
                <span>从这里开始是未读回复</span>
              </div>

              <component
                :is="resolvePostComponent(post)"
                :post="post"
                :discussion="discussion"
                :auth-store="authStore"
                :is-target="highlightedPostNumber === post.number"
                :is-suspended="isSuspended"
                :is-post-menu-open="activePostMenuId === post.id"
                :like-pending="likePendingPostIds.includes(post.id)"
                :flag-pending="flagPendingPostIds.includes(post.id)"
                :can-like-post="canLikePost"
                :can-edit-post="canEditPost"
                :can-delete-post="canDeletePost"
                :can-report-post="canReportPost"
                :can-moderate-pending-post="canModeratePendingPost"
                :has-post-controls="hasPostControls"
                :build-user-path="buildUserPath"
                :get-user-display-name="getUserDisplayName"
                :get-user-avatar-color="getUserAvatarColor"
                :get-user-initial="getUserInitial"
                :get-user-primary-group-icon="getUserPrimaryGroupIcon"
                :get-user-primary-group-color="getUserPrimaryGroupColor"
                :get-user-primary-group-label="getUserPrimaryGroupLabel"
                :format-absolute-date="formatAbsoluteDate"
                :format-date="formatDate"
                :format-like-summary="formatLikeSummary"
                :post-menu-items="getPostMenuOptions(post)"
                @jump-to-post="jumpToPost"
                @toggle-like="toggleLike"
                @reply-to-post="replyToPost"
                @toggle-post-menu="togglePostMenu"
                @edit-post="post => handlePostMenuSelection(post, 'edit-post')"
                @delete-post="post => handlePostMenuSelection(post, 'delete-post')"
                @toggle-hide-post="post => handlePostMenuSelection(post, 'toggle-hide-post')"
                @open-report-modal="post => handlePostMenuSelection(post, 'open-report-modal')"
                @moderate-post="({ post: targetPost, action }) => moderatePost(targetPost, action)"
                @resolve-post-flags="({ post: targetPost, status }) => resolvePostFlags(targetPost, status)"
                @close-post-menu="activePostMenuId = null"
              />
            </template>
          </div>

          <!-- 加载更多 -->
          <div v-if="hasMore" ref="nextTrigger" class="load-more">
            <ForumLoadMoreButton
              compact
              :loading="loadingMore"
              text="加载更多回复"
              loading-text="正在加载回复..."
              @click="loadMorePosts"
            />
          </div>

          <DiscussionReplyState
            :auth-store="authStore"
            :discussion="discussion"
            :is-suspended="isSuspended"
            :suspension-notice="suspensionNotice"
            :has-active-composer="hasActiveComposer"
            @open-composer="openComposer"
          />
        </main>

        <DiscussionSidebar
          v-if="discussion"
          ref="discussionSidebarRef"
          :discussion="discussion"
          :auth-store="authStore"
          :is-suspended="isSuspended"
          :suspension-notice="suspensionNotice"
          :has-active-composer="hasActiveComposer"
          :can-show-discussion-menu="canShowDiscussionMenu"
          :can-edit-discussion="canEditDiscussion"
          :can-moderate-discussion-settings="canModerateDiscussionSettings"
          :show-discussion-menu="showDiscussionMenu"
          :toggling-subscription="togglingSubscription"
          :menu-items="discussionMenuItems"
          :scrubber-scrollbar-style="scrubberScrollbarStyle"
          :scrubber-before-percent="scrubberBeforePercent"
          :scrubber-after-percent="scrubberAfterPercent"
          :scrubber-handle-percent="scrubberHandlePercent"
          :scrubber-dragging="scrubberDragging"
          :unread-count="unreadCount"
          :unread-top-percent="unreadTopPercent"
          :unread-height-percent="unreadHeightPercent"
          :scrubber-position-text="scrubberPositionText"
          :scrubber-description="scrubberDescription"
          :max-post-number="maxPostNumber"
          @primary-action="openComposer"
          @login-action="goToLoginForReply"
          @toggle-subscription="toggleSubscription"
          @toggle-menu="toggleDiscussionMenu"
          @menu-action="handleDiscussionMenuSelection"
          @jump-to-post="jumpToPost"
          @scrubber-track-click="handleScrubberTrackClick"
          @scrubber-handle-pointerdown="handleScrubberMouseDown"
        />
      </div>
    </div>

  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ForumLoadMoreButton from '@/components/forum/ForumLoadMoreButton.vue'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import { useForumStore } from '@/stores/forum'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useModalStore } from '@/stores/modal'
import DiscussionHero from '@/components/discussion/DiscussionHero.vue'
import DiscussionMobileActions from '@/components/discussion/DiscussionMobileActions.vue'
import DiscussionReplyState from '@/components/discussion/DiscussionReplyState.vue'
import DiscussionSidebar from '@/components/discussion/DiscussionSidebar.vue'
import { getPostTypeDefinition } from '@/forum/postTypes'
import { useDiscussionDetailInteractions } from '@/composables/useDiscussionDetailInteractions'
import { useDiscussionDetailMenus } from '@/composables/useDiscussionDetailMenus'
import { useDiscussionDetailPage } from '@/composables/useDiscussionDetailPage'
import { useDiscussionDetailPresentation } from '@/composables/useDiscussionDetailPresentation'
import {
  buildTagPath,
  buildUserPath,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial
} from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const modalStore = useModalStore()

const {
  activePostMenuId,
  discussion,
  discussionMobileNavRef,
  discussionSidebarRef,
  hasActiveComposer,
  hasMore,
  hasPrevious,
  handleScrubberMouseDown,
  handleScrubberTrackClick,
  highlightedPostNumber,
  jumpToPost,
  loadMorePosts,
  loading,
  loadingMore,
  loadingPrevious,
  loadPreviousPosts,
  maxPostNumber,
  nextTrigger,
  posts,
  previousTrigger,
  refreshDiscussion,
  scrollToPost,
  scrubberAfterPercent,
  scrubberBeforePercent,
  scrubberDescription,
  scrubberDragging,
  scrubberHandlePercent,
  scrubberPositionText,
  scrubberScrollbarStyle,
  showDiscussionMenu,
  showUnreadDivider,
  toggleDiscussionMenu,
  togglePostMenu,
  totalPosts,
  unreadCount,
  unreadHeightPercent,
  unreadTopPercent,
  upsertPost
} = useDiscussionDetailPage({
  authStore,
  composerStore,
  route,
  router
})
const {
  canDeletePost,
  canEditDiscussion,
  canEditPost,
  canLikePost,
  canModerateDiscussionSettings,
  canModeratePostVisibility,
  canModeratePendingDiscussion,
  canModeratePendingPost,
  canReplyFromMenu,
  canReportPost,
  canShowDiscussionMenu,
  deleteDiscussion,
  deletePost,
  editDiscussion,
  editPost,
  flagPendingPostIds,
  formatAbsoluteDate,
  formatDate,
  formatLikeSummary,
  goToLoginForReply,
  isSuspended,
  likePendingPostIds,
  moderateDiscussion,
  moderatePost,
  openComposer,
  openReportModal,
  replyToPost,
  resolvePostFlags,
  suspensionNotice,
  toggleHide,
  toggleLike,
  toggleLock,
  togglePin,
  togglePostHidden,
  toggleSubscription,
  togglingSubscription
} = useDiscussionDetailInteractions({
  authStore,
  composerStore,
  discussion,
  hasActiveComposer,
  modalStore,
  posts,
  refreshDiscussion,
  route,
  router,
  scrollToPost,
  totalPosts,
  upsertPost
})
const {
  discussionHeaderStyle,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupLabel
} = useDiscussionDetailPresentation(discussion)
const {
  discussionMenuItems,
  getPostMenuOptions,
  handleDiscussionMenuSelection,
  handlePostMenuSelection,
  hasPostControls,
  handleOpenReportModal
} = useDiscussionDetailMenus({
  activePostMenuId,
  authStore,
  canDeletePost,
  canEditPost,
  canModeratePostVisibility,
  canReportPost,
  canEditDiscussion,
  canModerateDiscussionSettings,
  canReplyFromMenu,
  discussion,
  deleteDiscussion,
  deletePost,
  editDiscussion,
  editPost,
  goToLoginForReply,
  hasActiveComposer,
  isSuspended,
  modalStore,
  openComposer,
  openReportModal,
  showDiscussionMenu,
  togglingSubscription,
  toggleHide,
  toggleLock,
  togglePin,
  togglePostHidden,
  toggleSubscription
})

function resolvePostComponent(post) {
  return getPostTypeDefinition(post?.type)?.component
}

watch(
  discussion,
  value => {
    if (!value) return
    const firstPostText = String(value.first_post?.content || value.excerpt || '').replace(/\s+/g, ' ').trim()
    forumStore.setPageMeta({
      title: value.title,
      description: firstPostText.slice(0, 160),
      ogType: 'article',
      canonicalUrl: `/d/${value.id}`,
    })
  },
  { immediate: true }
)

</script>

<style scoped>
.discussion-detail-page {
  padding: var(--forum-space-7) 0;
  background: var(--forum-bg-canvas);
  min-height: calc(100vh - 200px);
}

.layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--forum-space-7);
}

.main-content {
  background: var(--forum-bg-elevated);
  padding: var(--forum-space-7);
  border-radius: var(--forum-radius-md);
  box-shadow: var(--forum-shadow-sm);
}

.posts {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 30px;
}

.post-unread-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 10px 0 4px;
  color: var(--forum-accent-strong);
  font-size: var(--forum-font-size-xs);
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.post-unread-divider::before,
.post-unread-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(231, 103, 46, 0.28);
}

.load-more {
  text-align: center;
  margin-bottom: 30px;
}

.load-previous {
  margin-top: -10px;
}

.discussion-state-block {
  margin: 0;
}

@media (max-width: 768px) {
  .discussion-detail-page {
    padding: 0 0 24px;
  }

  .layout {
    display: block;
  }

  .main-content {
    padding: 0 0 20px;
    border-radius: 0;
    background: var(--forum-bg-elevated);
  }

  .sidebar {
    display: none;
  }

  .posts,
  .load-more {
    margin-left: 15px;
    margin-right: 15px;
  }
}
</style>
