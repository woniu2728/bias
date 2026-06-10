import { computed } from '@bias/core'

export function createDiscussionDetailViewBindings({
  activePostMenuId,
  authStore,
  buildUserPath,
  canDeletePost,
  canEditDiscussion,
  canEditPost,
  canModerateDiscussionSettings,
  canReportPost,
  canReplyFromMenu,
  canShowDiscussionMenu,
  closePostMenu,
  discussion,
  discussionBadges,
  discussionHeaderStyle,
  discussionMenuItems,
  discussionMobileActionItems = { value: [] },
  discussionMobileNavRef,
  discussionSidebarActionItems,
  discussionSidebarRef,
  editDiscussion,
  formatAbsoluteDate,
  formatDate,
  forumStore,
  getPostFeedbackActions,
  getPostMenuOptions,
  getPostPrimaryActions,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
  handleDiscussionMenuSelection,
  handlePostActionSelection,
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
  togglePostMenu,
  unreadCount,
  unreadDividerText,
  unreadHeightPercent,
  unreadTopPercent,
}) {
  const runPostActionSelection = handlePostActionSelection || handlePostMenuSelection

  const stateBindings = computed(() => ({
    loading: loading.value,
    loadingStateText: loadingStateText.value,
    discussion: discussion.value,
    missingStateText: missingStateText.value,
  }))

  const heroBindings = computed(() => ({
    authStore,
    discussion: discussion.value,
    discussionBadges: discussionBadges.value,
    discussionHeaderStyle: discussionHeaderStyle.value,
    canEditDiscussion: canEditDiscussion.value,
  }))

  const heroEvents = {
    editDiscussion,
    moderateDiscussion,
  }

  const mobileBindings = computed(() => ({
    discussionMobileNavRef,
    discussion: discussion.value,
    authStore,
    forumStore,
    isSuspended: isSuspended.value,
    showDiscussionMenu: showDiscussionMenu.value,
    canReplyFromMenu: canReplyFromMenu.value,
    hasActiveComposer: hasActiveComposer.value,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    scrubberPositionText: scrubberPositionText.value,
    scrubberDescription: scrubberDescription.value,
    unreadCount: unreadCount.value,
    unreadStartPostNumber: unreadCount.value ? Math.max(1, maxPostNumber.value - unreadCount.value + 1) : null,
    maxPostNumber: maxPostNumber.value,
    menuItems: discussionMenuItems.value,
    secondaryAction: discussionMobileActionItems.value[0] || null,
  }))

  const mobileEvents = {
    openComposer,
    openLoginForReply: handleDiscussionMenuSelection.bind(null, 'login'),
    secondaryAction: handleDiscussionMenuSelection,
    shareDiscussion,
    toggleDiscussionMenu,
    menuAction: handleDiscussionMenuSelection,
    jumpToPost,
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
    canEditPost,
    canDeletePost,
    canReportPost,
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
    showUnreadDivider,
    resolvePostComponent,
    hasPostControls,
    getPostFeedbackActions,
    getPostMenuOptions,
    getPostPrimaryActions,
    isTargetPost(post) {
      return highlightedPostNumber.value === post.number
    },
    isPostMenuOpen(post) {
      return activePostMenuId.value === post.id
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
    togglePostMenu,
    postAction({ post, action, ...context }) {
      return runPostActionSelection(post, action, context)
    },
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
