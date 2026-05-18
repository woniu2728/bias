import { computed } from 'vue'

export function createDiscussionDetailViewBindings({
  activePostMenuId,
  authStore,
  buildTagPath,
  buildUserPath,
  canDeletePost,
  canEditDiscussion,
  canEditPost,
  canLikePost,
  canModerateDiscussionSettings,
  canModeratePendingDiscussion,
  canModeratePendingPost,
  canReportPost,
  canReplyFromMenu,
  canShowDiscussionMenu,
  closePostMenu,
  discussion,
  discussionBadges,
  discussionHeaderStyle,
  discussionMenuItems,
  discussionMobileNavRef,
  discussionSidebarActionItems,
  discussionSidebarRef,
  editDiscussion,
  flagPendingPostIds,
  formatAbsoluteDate,
  formatDate,
  formatLikeSummary,
  getPostMenuOptions,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
  handleDiscussionMenuSelection,
  handlePostMenuSelection,
  handleScrubberMouseDown,
  handleScrubberTrackClick,
  hasActiveComposer,
  hasMore,
  hasPendingNewReplies,
  hasPostControls,
  hasPrevious,
  highlightedPostNumber,
  isSuspended,
  jumpToPost,
  likePendingPostIds,
  loadPendingNewReplies,
  loadMorePosts,
  loading,
  loadingMore,
  loadingPostsText,
  loadingPrevious,
  loadPreviousPosts,
  loadMoreText,
  loadPreviousText,
  loadingStateText,
  maxPostNumber,
  missingStateText,
  moderateDiscussion,
  moderatePost,
  nextTrigger,
  openComposer,
  pendingNewReplyCount,
  shareDiscussion,
  posts,
  previousTrigger,
  replyToPost,
  resolvePostComponent,
  resolvePostFlags,
  scrubberAfterPercent,
  scrubberBeforePercent,
  scrubberDescription,
  scrubberDragging,
  scrubberHandlePercent,
  scrubberPositionText,
  scrubberScrollbarStyle,
  showDiscussionMenu,
  showUnreadDivider,
  suspensionNotice,
  toggleDiscussionMenu,
  toggleSubscription,
  toggleLike,
  togglePostMenu,
  togglingSubscription,
  unreadCount,
  unreadDividerText,
  unreadHeightPercent,
  unreadTopPercent,
}) {
  const stateBindings = computed(() => ({
    loading: loading.value,
    loadingStateText: loadingStateText.value,
    discussion: discussion.value,
    missingStateText: missingStateText.value,
  }))

  const heroBindings = computed(() => ({
    discussion: discussion.value,
    discussionBadges: discussionBadges.value,
    discussionHeaderStyle: discussionHeaderStyle.value,
    canModeratePendingDiscussion: canModeratePendingDiscussion.value,
    canEditDiscussion: canEditDiscussion.value,
    buildTagPath,
  }))

  const heroEvents = {
    editDiscussion,
    moderateDiscussion,
  }

  const mobileBindings = computed(() => ({
    discussionMobileNavRef,
    discussion: discussion.value,
    authStore,
    isSuspended: isSuspended.value,
    showDiscussionMenu: showDiscussionMenu.value,
    canReplyFromMenu: canReplyFromMenu.value,
    hasActiveComposer: hasActiveComposer.value,
    togglingSubscription: togglingSubscription.value,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    menuItems: discussionMenuItems.value,
  }))

  const mobileEvents = {
    openComposer,
    openLoginForReply: handleDiscussionMenuSelection.bind(null, 'login'),
    shareDiscussion,
    toggleDiscussionMenu,
    toggleSubscription,
    menuAction: handleDiscussionMenuSelection,
  }

  const postStreamBindings = computed(() => ({
    previousTrigger,
    hasPrevious: hasPrevious.value,
    loadingPrevious: loadingPrevious.value,
    loadPreviousText: loadPreviousText.value,
    loadingPostsText: loadingPostsText.value,
    discussion: discussion.value,
    posts: posts.value,
    authStore,
    highlightedPostNumber: highlightedPostNumber.value,
    isSuspended: isSuspended.value,
    activePostMenuId: activePostMenuId.value,
    canLikePost: canLikePost.value,
    canEditPost: canEditPost.value,
    canDeletePost: canDeletePost.value,
    canReportPost: canReportPost.value,
    canModeratePendingPost: canModeratePendingPost.value,
    unreadDividerText: unreadDividerText.value,
    hasPendingNewReplies: hasPendingNewReplies(),
    hasMore: hasMore.value,
    nextTrigger,
    loadingMore: loadingMore.value,
    loadMoreText: loadMoreText.value,
    pendingNewReplyCount: pendingNewReplyCount.value,
    hasActiveComposer: hasActiveComposer.value,
    suspensionNotice: suspensionNotice.value,
    buildUserPath,
    getUserDisplayName,
    getUserAvatarColor,
    getUserInitial,
    getUserPrimaryGroupIcon,
    getUserPrimaryGroupColor,
    getUserPrimaryGroupLabel,
    formatAbsoluteDate,
    formatDate,
    formatLikeSummary,
    showUnreadDivider,
    resolvePostComponent,
    hasPostControls,
    getPostMenuOptions,
    isTargetPost(post) {
      return highlightedPostNumber.value === post.number
    },
    isPostMenuOpen(post) {
      return activePostMenuId.value === post.id
    },
    isLikePending(post) {
      return likePendingPostIds.value.includes(post.id)
    },
    isFlagPending(post) {
      return flagPendingPostIds.value.includes(post.id)
    },
  }))

  const postStreamEvents = {
    closePostMenu,
    jumpToPost,
    loadPendingNewReplies,
    loadMorePosts,
    loadPreviousPosts,
    openComposer,
    replyToPost,
    toggleLike,
    togglePostMenu,
    editPost(post) {
      return handlePostMenuSelection(post, 'edit-post')
    },
    deletePost(post) {
      return handlePostMenuSelection(post, 'delete-post')
    },
    toggleHidePost(post) {
      return handlePostMenuSelection(post, 'toggle-hide-post')
    },
    openReportModal(post) {
      return handlePostMenuSelection(post, 'open-report-modal')
    },
    moderatePost({ post, action }) {
      return moderatePost(post, action)
    },
    resolvePostFlags({ post, status }) {
      return resolvePostFlags(post, status)
    },
  }

  const sidebarBindings = computed(() => ({
    discussionSidebarRef,
    discussion: discussion.value,
    authStore,
    isSuspended: isSuspended.value,
    suspensionNotice: suspensionNotice.value,
    hasActiveComposer: hasActiveComposer.value,
    canShowDiscussionMenu: canShowDiscussionMenu.value,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    showDiscussionMenu: showDiscussionMenu.value,
    togglingSubscription: togglingSubscription.value,
    menuItems: discussionMenuItems.value,
    sidebarActionItems: discussionSidebarActionItems.value,
    scrubberScrollbarStyle: scrubberScrollbarStyle.value,
    scrubberBeforePercent: scrubberBeforePercent.value,
    scrubberAfterPercent: scrubberAfterPercent.value,
    scrubberHandlePercent: scrubberHandlePercent.value,
    scrubberDragging: scrubberDragging.value,
    unreadCount: unreadCount.value,
    unreadTopPercent: unreadTopPercent.value,
    unreadHeightPercent: unreadHeightPercent.value,
    scrubberPositionText: scrubberPositionText.value,
    scrubberDescription: scrubberDescription.value,
    maxPostNumber: maxPostNumber.value,
  }))

  const sidebarEvents = {
    jumpToPost,
    menuAction: handleDiscussionMenuSelection,
    scrubberHandlePointerdown: handleScrubberMouseDown,
    scrubberTrackClick: handleScrubberTrackClick,
    sidebarAction: handleDiscussionMenuSelection,
    toggleMenu: toggleDiscussionMenu,
  }

  return {
    heroBindings,
    heroEvents,
    mobileBindings,
    mobileEvents,
    postStreamBindings,
    postStreamEvents,
    sidebarBindings,
    sidebarEvents,
    stateBindings,
  }
}

export function useDiscussionDetailViewBindings(options) {
  return createDiscussionDetailViewBindings(options)
}
