<template>
  <div class="discussion-detail-page">
    <div class="container">
      <ForumStateBlock v-if="stateBindings.loading" class="discussion-state-block">{{ stateBindings.loadingStateText }}</ForumStateBlock>
      <ForumStateBlock v-else-if="!stateBindings.discussion" class="discussion-state-block">{{ stateBindings.missingStateText }}</ForumStateBlock>
      <div v-else class="layout">
        <!-- 主内容区 -->
        <main class="main-content">
          <DiscussionHero
            :discussion="heroBindings.discussion"
            :auth-store="heroBindings.authStore"
            :discussion-badges="heroBindings.discussionBadges"
            :discussion-header-style="heroBindings.discussionHeaderStyle"
            :can-edit-discussion="heroBindings.canEditDiscussion"
            @moderate-discussion="heroEvents.moderateDiscussion"
            @edit-discussion="heroEvents.editDiscussion"
          />

          <DiscussionMobileActions
            :ref="mobileBindings.discussionMobileNavRef"
            :discussion="mobileBindings.discussion"
            :auth-store="mobileBindings.authStore"
            :is-suspended="mobileBindings.isSuspended"
            :show-discussion-menu="mobileBindings.showDiscussionMenu"
            :can-reply-from-menu="mobileBindings.canReplyFromMenu"
            :has-active-composer="mobileBindings.hasActiveComposer"
            :can-edit-discussion="mobileBindings.canEditDiscussion"
            :can-moderate-discussion-settings="mobileBindings.canModerateDiscussionSettings"
            :menu-items="mobileBindings.menuItems"
            :secondary-action="mobileBindings.secondaryAction"
            @open-composer="mobileEvents.openComposer"
            @open-login-for-reply="mobileEvents.openLoginForReply"
            @secondary-action="mobileEvents.secondaryAction"
            @share-discussion="mobileEvents.shareDiscussion"
            @toggle-menu="mobileEvents.toggleDiscussionMenu"
            @menu-action="mobileEvents.menuAction"
            @jump-to-post="postStreamEvents.jumpToPost"
          />

          <div v-if="postStreamBindings.hasPrevious" :ref="postStreamBindings.previousTrigger" class="load-more load-previous">
            <ForumLoadMoreButton
              compact
              :loading="postStreamBindings.loadingPrevious"
              :text="postStreamBindings.loadPreviousText"
              :loading-text="postStreamBindings.loadingPostsText"
              @click="postStreamEvents.loadPreviousPosts"
            />
          </div>

          <!-- 帖子列表 -->
          <div class="posts">
            <template v-for="post in postStreamBindings.posts" :key="post.id">
              <div
                v-if="postStreamBindings.showUnreadDivider(post)"
                class="post-unread-divider"
              >
                <span>{{ postStreamBindings.unreadDividerText }}</span>
              </div>

              <component
                :is="postStreamBindings.resolvePostComponent(post)"
                :post="post"
                :discussion="postStreamBindings.discussion"
                :auth-store="postStreamBindings.authStore"
                :is-target="postStreamBindings.isTargetPost(post)"
                :is-suspended="postStreamBindings.isSuspended"
                :is-post-menu-open="postStreamBindings.isPostMenuOpen(post)"
                :can-edit-post="postStreamBindings.canEditPost"
                :can-delete-post="postStreamBindings.canDeletePost"
                :can-report-post="postStreamBindings.canReportPost"
                :has-post-controls="postStreamBindings.hasPostControls"
                :build-user-path="postStreamBindings.buildUserPath"
                :get-user-display-name="postStreamBindings.getUserDisplayName"
                :get-user-avatar-color="postStreamBindings.getUserAvatarColor"
                :get-user-initial="postStreamBindings.getUserInitial"
                :get-user-primary-group-icon="postStreamBindings.getUserPrimaryGroupIcon"
                :get-user-primary-group-color="postStreamBindings.getUserPrimaryGroupColor"
                :get-user-primary-group-label="postStreamBindings.getUserPrimaryGroupLabel"
                :format-absolute-date="postStreamBindings.formatAbsoluteDate"
                :format-date="postStreamBindings.formatDate"
                :post-primary-actions="postStreamBindings.getPostPrimaryActions(post)"
                :post-feedback-actions="postStreamBindings.getPostFeedbackActions(post)"
                :post-menu-items="postStreamBindings.getPostMenuOptions(post)"
                @jump-to-post="postStreamEvents.jumpToPost"
                @reply-to-post="postStreamEvents.replyToPost"
                @post-action="postStreamEvents.postAction"
                @toggle-post-menu="postStreamEvents.togglePostMenu"
                @edit-post="postStreamEvents.editPost"
                @delete-post="postStreamEvents.deletePost"
                @toggle-hide-post="postStreamEvents.toggleHidePost"
                @open-report-modal="postStreamEvents.openReportModal"
                @moderate-post="postStreamEvents.moderatePost"
                @close-post-menu="postStreamEvents.closePostMenu"
              />
            </template>
          </div>

          <ForumInlineMessage
            v-if="postStreamBindings.hasPendingNewReplies"
            tone="info"
            class="discussion-new-replies-banner"
          >
            <button type="button" class="discussion-new-replies-button" @click="postStreamEvents.loadPendingNewReplies">
              已有 {{ postStreamBindings.pendingNewReplyCount }} 条新回复，点击加载
            </button>
          </ForumInlineMessage>

          <!-- 加载更多 -->
          <div v-if="postStreamBindings.hasMore" :ref="postStreamBindings.nextTrigger" class="load-more">
            <ForumLoadMoreButton
              compact
              :loading="postStreamBindings.loadingMore"
              :text="postStreamBindings.loadMoreText"
              :loading-text="postStreamBindings.loadingPostsText"
              @click="postStreamEvents.loadMorePosts"
            />
          </div>

          <DiscussionReplyState
            :auth-store="postStreamBindings.authStore"
            :discussion="postStreamBindings.discussion"
            :is-suspended="postStreamBindings.isSuspended"
            :suspension-notice="postStreamBindings.suspensionNotice"
            :has-active-composer="postStreamBindings.hasActiveComposer"
            :typing-discussion-id="postStreamBindings.typingDiscussionId"
            @open-composer="postStreamEvents.openComposer"
          />
        </main>

        <DiscussionSidebar
          v-if="sidebarBindings.discussion"
          :ref="sidebarBindings.discussionSidebarRef"
          :discussion="sidebarBindings.discussion"
          :auth-store="sidebarBindings.authStore"
          :forum-store="sidebarBindings.forumStore"
          :is-suspended="sidebarBindings.isSuspended"
          :suspension-notice="sidebarBindings.suspensionNotice"
          :has-active-composer="sidebarBindings.hasActiveComposer"
          :can-show-discussion-menu="sidebarBindings.canShowDiscussionMenu"
          :can-edit-discussion="sidebarBindings.canEditDiscussion"
          :can-moderate-discussion-settings="sidebarBindings.canModerateDiscussionSettings"
          :show-discussion-menu="sidebarBindings.showDiscussionMenu"
          :menu-items="sidebarBindings.menuItems"
          :sidebar-action-items="sidebarBindings.sidebarActionItems"
          :scrubber-scrollbar-style="sidebarBindings.scrubberScrollbarStyle"
          :scrubber-before-percent="sidebarBindings.scrubberBeforePercent"
          :scrubber-after-percent="sidebarBindings.scrubberAfterPercent"
          :scrubber-handle-percent="sidebarBindings.scrubberHandlePercent"
          :scrubber-dragging="sidebarBindings.scrubberDragging"
          :unread-count="sidebarBindings.unreadCount"
          :unread-top-percent="sidebarBindings.unreadTopPercent"
          :unread-height-percent="sidebarBindings.unreadHeightPercent"
          :scrubber-position-text="sidebarBindings.scrubberPositionText"
          :scrubber-description="sidebarBindings.scrubberDescription"
          :max-post-number="sidebarBindings.maxPostNumber"
          @sidebar-action="sidebarEvents.sidebarAction"
          @toggle-menu="sidebarEvents.toggleMenu"
          @menu-action="sidebarEvents.menuAction"
          @jump-to-post="sidebarEvents.jumpToPost"
          @scrubber-track-click="sidebarEvents.scrubberTrackClick"
          @scrubber-handle-pointerdown="sidebarEvents.scrubberHandlePointerdown"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  useAuthStore } from '@bias/users'
import { useRouter,
  useRoute,
  useModalStore
} from '@bias/core'
import {
  ForumInlineMessage,
  ForumLoadMoreButton,
  ForumStateBlock,
  useComposerStore,
  useForumStore
} from '@bias/forum'
import DiscussionHero from './components/DiscussionHero.vue'
import DiscussionMobileActions from './components/DiscussionMobileActions.vue'
import DiscussionReplyState from './components/DiscussionReplyState.vue'
import DiscussionSidebar from './components/DiscussionSidebar.vue'
import { useDiscussionDetailViewModel } from './useDiscussionDetailViewModel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const modalStore = useModalStore()

const {
  heroBindings,
  heroEvents,
  mobileBindings,
  mobileEvents,
  postStreamBindings,
  postStreamEvents,
  sidebarBindings,
  sidebarEvents,
  stateBindings,
} = useDiscussionDetailViewModel({
  authStore,
  composerStore,
  forumStore,
  modalStore,
  route,
  router
})
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

.discussion-new-replies-banner {
  margin-top: -6px;
}

.discussion-new-replies-button {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.discussion-new-replies-button:hover {
  opacity: 0.84;
}

.load-previous {
  margin-top: -10px;
}

.discussion-state-block {
  margin: 0;
}

@media (max-width: 768px) {
  .discussion-detail-page {
    padding: 0 0 90px;
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
