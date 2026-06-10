
import { computed } from '@bias/core'
import { useDiscussionDetailPageLifecycle } from './useDiscussionDetailPageLifecycle'
import { useDiscussionDetailState } from './useDiscussionDetailState'
import { useDiscussionPostViewportState } from './useDiscussionPostViewportState'
import { useDiscussionSidebarScrubber } from './useDiscussionSidebarScrubber'
import { useDiscussionDetailUiState } from './useDiscussionDetailUiState'

export function useDiscussionDetailPage({
  authStore,
  composerStore,
  forumStore,
  route,
  router
}) {
  const detailState = useDiscussionDetailState({
    authStore,
    forumStore,
    route,
    router,
  })
  const discussion = detailState.discussion
  const {
    currentVisiblePostNumber,
    currentVisiblePostProgress,
    hasMore,
    hasPendingNewReplies,
    hasPrevious,
    highlightedPostNumber,
    jumpToPost,
    loadMorePosts,
    loadPendingNewReplies,
    loading,
    loadingMore,
    loadingPrevious,
    loadPreviousPosts,
    maxPostNumber,
    pendingNewReplyCount,
    posts,
    removePost,
    resetPostStream,
    scheduleNearUrlSync,
    scheduleReadStateSync,
    scrollToPost,
    syncWindowToRouteNear,
    setCurrentVisiblePostNumber,
    setCurrentVisiblePostProgress,
    showUnreadDivider,
    totalPosts,
    typingDiscussionId,
    unreadCount,
    unreadStartPostNumber,
    upsertPost,
  } = detailState.postStream
  const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
  const uiState = useDiscussionDetailUiState({
    authStore,
    composerStore,
    currentVisiblePostProgress,
    discussion,
    isSuspended,
    maxPostNumber,
  })
  const {
    activePostMenuId,
    attachGlobalListeners,
    closePostMenu,
    detachGlobalListeners,
    discussionMobileNavRef,
    hasActiveComposer,
    hasMobileDiscussionMenuActions,
    resetMobileHeader,
    resetTransientUiState,
    showDiscussionMenu,
    syncMobileHeader,
    toggleDiscussionMenu,
    togglePostMenu,
  } = uiState
  const scrubberState = useDiscussionSidebarScrubber({
    currentVisiblePostNumber,
    currentVisiblePostProgress,
    jumpToPost,
    maxPostNumber,
    posts,
    unreadCount,
    unreadStartPostNumber,
  })
  const {
    discussionSidebarRef,
    handleScrubberMouseDown,
    handleScrubberTrackClick,
    resetScrubberPreview,
    scrubberAfterPercent,
    scrubberBeforePercent,
    scrubberDescription,
    scrubberDragging,
    scrubberHandlePercent,
    scrubberPositionText,
    scrubberScrollbarStyle,
    syncScrubberTrackMetrics,
    unreadHeightPercent,
    unreadTopPercent,
  } = scrubberState
  const viewportState = useDiscussionPostViewportState({
    currentVisiblePostNumber,
    hasMore,
    hasPrevious,
    loadingMore,
    loadingPrevious,
    loadMorePosts,
    loadPreviousPosts,
    maxPostNumber,
    posts,
    scheduleNearUrlSync,
    scheduleReadStateSync,
    setCurrentVisiblePostNumber,
    setCurrentVisiblePostProgress,
    syncScrubberTrackMetrics,
  })
  const {
    loadMorePostsAndSync,
    loadPreviousPostsWithAnchor,
    nextTrigger,
    previousTrigger,
    updateVisiblePostFromScroll,
  } = viewportState

  async function refreshDiscussion() {
    await detailState.refreshDiscussion({ keepLoading: true })
  }

  useDiscussionDetailPageLifecycle({
    attachGlobalListeners,
    currentVisiblePostProgress,
    detachGlobalListeners,
    discussionTitle: computed(() => discussion.value?.title || ''),
    hasMobileDiscussionMenuActions,
    loading,
    maxPostNumber,
    refreshDiscussion,
    resetMobileHeader,
    resetPostStream,
    resetScrubberPreview,
    resetTransientUiState,
    route,
    syncNearPostWindow: syncWindowToRouteNear,
    syncMobileHeader,
    updateVisiblePostFromScroll,
  })

  return {
    activePostMenuId,
    closePostMenu,
    discussion,
    discussionMobileNavRef,
    discussionSidebarRef,
    hasActiveComposer,
    hasMore,
    hasPendingNewReplies,
    hasPrevious,
    handleScrubberMouseDown,
    handleScrubberTrackClick,
    highlightedPostNumber,
    jumpToPost,
    loadMorePosts: loadMorePostsAndSync,
    loadPendingNewReplies,
    loading,
    loadingMore,
    loadingPrevious,
    loadPreviousPosts: loadPreviousPostsWithAnchor,
    maxPostNumber,
    nextTrigger,
    pendingNewReplyCount,
    patchDiscussion: detailState.patchDiscussion,
    posts,
    previousTrigger,
    refreshDiscussion,
    removePost,
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
    typingDiscussionId,
    unreadCount,
    unreadHeightPercent,
    unreadTopPercent,
    upsertPost,
  }
}
