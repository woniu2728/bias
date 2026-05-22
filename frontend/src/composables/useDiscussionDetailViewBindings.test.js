import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { createDiscussionDetailViewBindings } from './useDiscussionDetailViewBindings.js'

function createBindings(overrides = {}) {
  return createDiscussionDetailViewBindings({
    activePostMenuId: ref(7),
    authStore: { isAuthenticated: true },
    buildDiscussionPath: value => `/d/${value.id || value}`,
    buildTagPath: value => `/tags/${value.slug || value}`,
    buildUserPath: value => `/u/${value.id || value}`,
    canDeletePost: () => true,
    canEditDiscussion: ref(true),
    canEditPost: () => true,
    canLikePost: () => true,
    canModerateDiscussionSettings: ref(true),
    canModeratePendingDiscussion: ref(false),
    canModeratePendingPost: () => false,
    canReportPost: () => true,
    canReplyFromMenu: ref(true),
    canShowDiscussionMenu: ref(true),
    closePostMenu() {},
    discussion: ref({ id: 1, title: '讨论' }),
    discussionBadges: ref([{ key: 'sticky' }]),
    discussionHeaderStyle: ref({ color: '#fff' }),
    discussionMenuItems: ref([{ key: 'reply' }]),
    discussionMobileNavRef: ref(null),
    discussionSidebarActionItems: ref([{ key: 'bookmark' }]),
    discussionSidebarRef: ref(null),
    editDiscussion() {},
    flagPendingPostIds: ref([9]),
    formatAbsoluteDate: value => value,
    formatDate: value => value,
    formatLikeSummary: value => value,
    getPostMenuOptions: post => [{ key: `post-${post.id}` }],
    getUserAvatarColor: () => '#000',
    getUserDisplayName: () => 'alice',
    getUserInitial: () => 'A',
    getUserPrimaryGroupColor: () => '#111',
    getUserPrimaryGroupIcon: () => 'icon',
    getUserPrimaryGroupLabel: () => '管理员',
    handleDiscussionMenuSelection() {},
    handlePostMenuSelection() {},
    handleScrubberMouseDown() {},
    handleScrubberTrackClick() {},
    hasActiveComposer: ref(false),
    hasMore: ref(true),
    hasPendingNewReplies: () => true,
    hasPostControls: () => true,
    hasPrevious: ref(true),
    highlightedPostNumber: ref(3),
    isSuspended: ref(false),
    jumpToPost() {},
    likePendingPostIds: ref([8]),
    loadPendingNewReplies() {},
    loadMorePosts() {},
    loading: ref(false),
    loadingMore: ref(false),
    loadingPostsText: ref('正在加载回复...'),
    loadingPrevious: ref(false),
    loadPreviousPosts() {},
    loadMoreText: ref('加载更多回复'),
    loadPreviousText: ref('加载前面的回复'),
    loadingStateText: ref('加载中...'),
    maxPostNumber: ref(20),
    missingStateText: ref('讨论不存在'),
    moderateDiscussion() {},
    moderatePost() {},
    nextTrigger: ref(null),
    openComposer() {},
    pendingNewReplyCount: ref(3),
    shareDiscussion() {},
    posts: ref([{ id: 8, number: 3 }, { id: 9, number: 4 }]),
    previousTrigger: ref(null),
    replyToPost() {},
    resolvePostComponent: () => 'PostItem',
    resolvePostFlags() {},
    scrubberAfterPercent: ref(60),
    scrubberBeforePercent: ref(40),
    scrubberDescription: ref('现在在 3 / 20'),
    scrubberDragging: ref(false),
    scrubberHandlePercent: ref(50),
    scrubberPositionText: ref('3 / 20'),
    scrubberScrollbarStyle: ref({ '--top': '10%' }),
    showDiscussionMenu: ref(false),
    showUnreadDivider: post => post.number === 4,
    suspensionNotice: ref('账号已停用'),
    toggleDiscussionMenu() {},
    toggleSubscription() {},
    toggleLike() {},
    togglePostMenu() {},
    togglingSubscription: ref(false),
    unreadCount: ref(2),
    unreadDividerText: ref('从这里开始是未读回复'),
    unreadHeightPercent: ref(20),
    unreadTopPercent: ref(30),
    ...overrides,
  })
}

test('discussion detail view bindings expose grouped bindings', () => {
  const bindings = createBindings()

  assert.equal(bindings.stateBindings.value.discussion.title, '讨论')
  assert.equal(bindings.heroBindings.value.discussionBadges[0].key, 'sticky')
  assert.equal(bindings.mobileBindings.value.menuItems[0].key, 'reply')
  assert.equal(bindings.mobileBindings.value.scrubberPositionText, '3 / 20')
  assert.equal(bindings.mobileBindings.value.unreadStartPostNumber, 19)
  assert.equal(bindings.postStreamBindings.value.isTargetPost({ number: 3 }), true)
  assert.equal(bindings.postStreamBindings.value.isLikePending({ id: 8 }), true)
  assert.equal(bindings.postStreamBindings.value.isFlagPending({ id: 9 }), true)
  assert.equal(bindings.postStreamBindings.value.hasPendingNewReplies, true)
  assert.equal(bindings.postStreamBindings.value.pendingNewReplyCount, 3)
  assert.equal(bindings.sidebarBindings.value.maxPostNumber, 20)
})

test('discussion detail view bindings expose stable event handlers', () => {
  const calls = []
  const bindings = createBindings({
    closePostMenu() {
      calls.push('close-post-menu')
    },
    editDiscussion() {
      calls.push('edit-discussion')
    },
    handleDiscussionMenuSelection(action) {
      calls.push(['discussion-menu', action])
    },
    handlePostMenuSelection(post, action) {
      calls.push(['post-menu', post.id, action])
    },
    handleScrubberMouseDown(event) {
      calls.push(['scrubber-down', event])
    },
    handleScrubberTrackClick(event) {
      calls.push(['scrubber-click', event])
    },
    jumpToPost(number) {
      calls.push(['jump', number])
    },
    loadMorePosts() {
      calls.push('load-more')
    },
    loadPendingNewReplies() {
      calls.push('load-pending')
    },
    loadPreviousPosts() {
      calls.push('load-previous')
    },
    moderateDiscussion(action) {
      calls.push(['moderate-discussion', action])
    },
    moderatePost(post, action) {
      calls.push(['moderate-post', post.id, action])
    },
    openComposer() {
      calls.push('open-composer')
    },
    shareDiscussion() {
      calls.push('share-discussion')
    },
    replyToPost(post) {
      calls.push(['reply', post.id])
    },
    resolvePostFlags(post, status) {
      calls.push(['resolve-flags', post.id, status])
    },
    toggleDiscussionMenu() {
      calls.push('toggle-menu')
    },
    toggleSubscription() {
      calls.push('toggle-subscription')
    },
    toggleLike(post) {
      calls.push(['like', post.id])
    },
    togglePostMenu(post) {
      calls.push(['toggle-post-menu', post.id])
    },
  })

  bindings.heroEvents.editDiscussion()
  bindings.heroEvents.moderateDiscussion('approve')
  bindings.mobileEvents.openComposer()
  bindings.mobileEvents.openLoginForReply()
  bindings.mobileEvents.shareDiscussion()
  bindings.mobileEvents.toggleSubscription()
  bindings.mobileEvents.toggleDiscussionMenu()
  bindings.mobileEvents.menuAction('reply')
  bindings.mobileEvents.jumpToPost(18)
  bindings.postStreamEvents.loadPreviousPosts()
  bindings.postStreamEvents.jumpToPost(12)
  bindings.postStreamEvents.toggleLike({ id: 3 })
  bindings.postStreamEvents.replyToPost({ id: 4 })
  bindings.postStreamEvents.togglePostMenu({ id: 5 })
  bindings.postStreamEvents.editPost({ id: 6 })
  bindings.postStreamEvents.deletePost({ id: 7 })
  bindings.postStreamEvents.toggleHidePost({ id: 8 })
  bindings.postStreamEvents.openReportModal({ id: 9 })
  bindings.postStreamEvents.moderatePost({ post: { id: 10 }, action: 'approve' })
  bindings.postStreamEvents.resolvePostFlags({ post: { id: 11 }, status: 'resolved' })
  bindings.postStreamEvents.closePostMenu()
  bindings.postStreamEvents.loadPendingNewReplies()
  bindings.postStreamEvents.loadMorePosts()
  bindings.postStreamEvents.openComposer()
  bindings.sidebarEvents.sidebarAction('bookmark')
  bindings.sidebarEvents.menuAction('reply')
  bindings.sidebarEvents.jumpToPost(13)
  bindings.sidebarEvents.scrubberTrackClick('track')
  bindings.sidebarEvents.scrubberHandlePointerdown('pointer')
  bindings.sidebarEvents.toggleMenu()

  assert.deepEqual(calls, [
    'edit-discussion',
    ['moderate-discussion', 'approve'],
    'open-composer',
    ['discussion-menu', 'login'],
    'share-discussion',
    'toggle-subscription',
    'toggle-menu',
    ['discussion-menu', 'reply'],
    ['jump', 18],
    'load-previous',
    ['jump', 12],
    ['like', 3],
    ['reply', 4],
    ['toggle-post-menu', 5],
    ['post-menu', 6, 'edit-post'],
    ['post-menu', 7, 'delete-post'],
    ['post-menu', 8, 'toggle-hide-post'],
    ['post-menu', 9, 'open-report-modal'],
    ['moderate-post', 10, 'approve'],
    ['resolve-flags', 11, 'resolved'],
    'close-post-menu',
    'load-pending',
    'load-more',
    'open-composer',
    ['discussion-menu', 'bookmark'],
    ['discussion-menu', 'reply'],
    ['jump', 13],
    ['scrubber-click', 'track'],
    ['scrubber-down', 'pointer'],
    'toggle-menu',
  ])
})
