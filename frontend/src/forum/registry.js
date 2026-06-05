import { defineAsyncComponent } from 'vue'
import api from '@/api'
import {
  buildDiscussionPath,
  buildUserPath,
  formatRelativeTime,
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  getUserAvatarColor,
  getUserInitial,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from '@/utils/forum'
import {
  resolveDiscussionAction,
  resolvePostAction,
  runDiscussionAction,
  runPostAction,
} from '@/forum/discussionActionRuntime'
import {
  getComposerNotices,
  getComposerSecondaryActions,
  getComposerDraftMeta,
  runComposerMentionProviders,
  runComposerPreviewTransformers,
  getComposerStatusItems,
  getComposerTools,
  getForumNavItems,
  getForumNavSections,
  getDiscussionActions,
  getDiscussionActionHandler,
  getPostActions,
  getPostActionHandler,
  getNotificationRenderers,
  getProfilePanels,
  getSearchSources,
  getDiscussionBadges,
  getDiscussionStateBadges,
  getHeroMetaItems,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getPostFlagPanel,
  getApprovalNote,
  getEmptyState,
  getPageState,
  getStateBlock,
  getUiCopy,
  getPostStateBadges,
  getPostReviewBanner,
  getUserBadges,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionBadge,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerHeroMeta,
  registerPostFlagPanel,
  registerApprovalNote,
  registerEmptyState,
  registerPageState,
  registerStateBlock,
  registerUiCopy,
  registerDiscussionStateBadge,
  registerPostStateBadge,
  registerPostReviewBanner,
  registerComposerNotice,
  registerComposerSecondaryAction,
  registerComposerDraftMeta,
  registerComposerMentionProvider,
  registerComposerPreviewTransformer,
  registerComposerStatusItem,
  registerComposerSubmitSuccess,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerHeaderItem,
  registerForumNavItem,
  registerForumNavSection,
  registerNotificationRenderer,
  registerProfilePanel,
  registerPostAction,
  registerPostActionHandler,
  registerSearchSource,
  registerUserBadge,
  runComposerSubmitGuards,
  runComposerSubmitSuccess,
} from '@/forum/frontendRegistry'
import { highlightSearchText } from '@/utils/search'
import { renderTwemojiHtml, setTwemojiBaseUrl, setTwemojiEnabled } from '@/utils/twemoji'
export { registerNotificationType } from './notificationTypes'
export { registerPostType } from './postTypes'
export { registerSearchFilter } from './searchFilters'
export { default as PostReportModal } from '@/components/modals/PostReportModal.vue'
export { api as forumApi }

export {
  getForumNavItems,
  getForumNavSections,
  getComposerNotices,
  getComposerSecondaryActions,
  getComposerDraftMeta,
  runComposerMentionProviders,
  runComposerPreviewTransformers,
  getComposerStatusItems,
  getComposerTools,
  resolveDiscussionAction,
  resolvePostAction,
  getDiscussionActions,
  getDiscussionActionHandler,
  getPostActions,
  getPostActionHandler,
  getNotificationRenderers,
  getDiscussionBadges,
  getDiscussionStateBadges,
  getHeroMetaItems,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getPostFlagPanel,
  getApprovalNote,
  getEmptyState,
  getPageState,
  getStateBlock,
  getUiCopy,
  getPostStateBadges,
  getPostReviewBanner,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionBadge,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerHeroMeta,
  registerPostFlagPanel,
  registerApprovalNote,
  registerEmptyState,
  registerPageState,
  registerStateBlock,
  registerUiCopy,
  registerDiscussionStateBadge,
  registerPostStateBadge,
  registerPostReviewBanner,
  registerComposerNotice,
  registerComposerSecondaryAction,
  registerComposerDraftMeta,
  registerComposerMentionProvider,
  registerComposerPreviewTransformer,
  registerComposerStatusItem,
  registerComposerSubmitSuccess,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerHeaderItem,
  registerForumNavItem,
  registerForumNavSection,
  registerNotificationRenderer,
  registerProfilePanel,
  registerPostAction,
  registerPostActionHandler,
  registerSearchSource,
  registerUserBadge,
  runDiscussionAction,
  runPostAction,
  runComposerSubmitGuards,
  runComposerSubmitSuccess,
  getProfilePanels,
  getSearchSources,
  getUserBadges,
  renderTwemojiHtml,
  setTwemojiBaseUrl,
  setTwemojiEnabled,
}

registerForumNavSection({
  key: 'primary',
  title: '',
  order: 10,
})

registerForumNavSection({
  key: 'personal',
  title: '个人',
  order: 20,
})

registerForumNavItem({
  key: 'home',
  moduleId: 'discussions',
  to: '/',
  icon: 'far fa-comments',
  label: '全部讨论',
  description: '查看全站最新讨论流。',
  section: 'primary',
  order: 10,
  surfaces: ['primary-nav', 'discussion-sidebar', 'mobile-drawer']
})

registerForumNavItem({
  key: 'profile',
  moduleId: 'users',
  to: ({ authStore }) => buildUserPath(authStore.user),
  icon: 'fas fa-user',
  label: '我的主页',
  description: '查看你的资料、讨论和回复。',
  section: 'personal',
  order: 50,
  surfaces: ['discussion-sidebar', 'mobile-drawer'],
  isVisible: ({ authStore }) => Boolean(authStore?.user)
})

function isOwnProfileRoute(route, user) {
  if (!route || !user) return false
  return route.name === 'profile'
    || (route.name === 'user-profile' && String(route.params.id) === String(user.id))
}

registerHeaderItem({
  key: 'user-profile-menu',
  moduleId: 'users',
  placement: 'user-menu',
  order: 10,
  icon: 'fas fa-user',
  label: '个人资料',
  to: ({ authStore }) => buildUserPath(authStore.user),
  isVisible: ({ authStore }) => Boolean(authStore?.user),
  isActive: ({ route, authStore }) => isOwnProfileRoute(route, authStore?.user),
})

registerHeaderItem({
  key: 'guest-login',
  placement: 'guest-actions',
  order: 10,
  label: '登录',
  isVisible: ({ authStore }) => !authStore?.user,
  onClick: ({ openLogin }) => openLogin?.(),
})

registerHeaderItem({
  key: 'guest-register',
  placement: 'guest-actions',
  order: 20,
  label: '注册',
  tone: 'primary',
  isVisible: ({ authStore }) => !authStore?.user,
  onClick: ({ openRegister }) => openRegister?.(),
})

registerHeaderItem({
  key: 'user-admin-menu',
  placement: 'user-menu',
  order: 30,
  icon: 'fas fa-cog',
  label: '管理后台',
  href: '/admin.html',
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
})

registerHeaderItem({
  key: 'user-logout-menu',
  placement: 'user-menu',
  order: 40,
  icon: 'fas fa-sign-out-alt',
  label: '登出',
  tone: 'danger',
  separated: true,
  isVisible: ({ authStore }) => Boolean(authStore?.user),
  onClick: ({ handleLogout }) => handleLogout?.(),
})

registerHeaderItem({
  key: 'mobile-profile',
  moduleId: 'users',
  placement: 'mobile-drawer-personal',
  order: 20,
  icon: 'fas fa-user',
  label: '我的主页',
  to: ({ authStore }) => buildUserPath(authStore.user),
  isVisible: ({ authStore }) => Boolean(authStore?.user),
  isActive: ({ route, authStore }) => isOwnProfileRoute(route, authStore?.user),
})

registerHeaderItem({
  key: 'mobile-admin',
  placement: 'mobile-drawer-user',
  order: 10,
  icon: 'fas fa-cog',
  label: '管理后台',
  href: '/admin.html',
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
})

registerHeaderItem({
  key: 'mobile-logout',
  placement: 'mobile-drawer-user',
  order: 20,
  icon: 'fas fa-sign-out-alt',
  label: '登出',
  tone: 'danger',
  isVisible: ({ authStore }) => Boolean(authStore?.user),
  onClick: ({ handleLogout }) => handleLogout?.(),
})

registerHeaderItem({
  key: 'mobile-guest-login',
  placement: 'mobile-drawer-auth',
  order: 10,
  label: '登录',
  isVisible: ({ authStore }) => !authStore?.user,
  onClick: ({ openLogin }) => openLogin?.(),
})

registerHeaderItem({
  key: 'mobile-guest-register',
  placement: 'mobile-drawer-auth',
  order: 20,
  label: '注册',
  tone: 'primary',
  isVisible: ({ authStore }) => !authStore?.user,
  onClick: ({ openRegister }) => openRegister?.(),
})

function registerDefaultNotificationRenderer(definition) {
  return registerNotificationRenderer({
    ...definition,
    key: definition.key || definition.type,
  })
}

function buildSearchTextHtml(value, query, limit) {
  return renderTwemojiHtml(highlightSearchText(value, query, limit))
}

registerDefaultNotificationRenderer({
  type: 'discussionCreated',
  moduleId: 'discussions',
  label: '发起讨论',
  icon: 'fas fa-pen',
  navigationScope: 'discussion',
  groupLabel: '讨论动态',
  order: 110,
  getText(notification) {
    const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
    const discussionTitle = notification?.data?.discussion_title || ''
    return `${fromUser} 发起了新讨论 "${discussionTitle}"`
  },
})

registerDefaultNotificationRenderer({
  type: 'postCreated',
  moduleId: 'posts',
  label: '发表回复',
  icon: 'fas fa-message',
  navigationScope: 'post',
  groupLabel: '讨论动态',
  order: 120,
  getText(notification) {
    const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
    return `${fromUser} 发表了新回复`
  },
})

registerSearchSource({
  key: 'discussions',
  moduleId: 'discussions',
  type: 'discussions',
  label: '讨论',
  routeType: 'discussions',
  apiType: 'discussions',
  filterTarget: 'discussion',
  icon: 'far fa-comments',
  order: 10,
  buildResultItems(items, { query }) {
    return items.map(discussion => ({
      key: `discussion-${discussion.id}`,
      avatarAlt: discussion.user?.display_name || discussion.user?.username || '',
      avatarColor: getUserAvatarColor(discussion.user),
      avatarMode: true,
      avatarText: discussion.user?.avatar_url ? '' : getUserInitial(discussion.user),
      avatarUrl: discussion.user?.avatar_url || '',
      excerptHtml: buildSearchTextHtml(discussion.excerpt || '这个讨论没有更多摘要。', query, 180),
      iconClass: 'far fa-comments',
      metaItems: [
        discussion.user?.display_name || discussion.user?.username || '未知用户',
        `${discussion.comment_count || 0} 回复`,
        formatRelativeTime(discussion.last_posted_at || discussion.created_at),
      ],
      path: buildDiscussionPath(discussion),
      titleHtml: buildSearchTextHtml(discussion.title || '讨论', query, 90),
      titleText: discussion.title || '讨论',
      userLayout: false,
    }))
  },
})

registerSearchSource({
  key: 'posts',
  moduleId: 'posts',
  type: 'posts',
  label: '帖子',
  routeType: 'posts',
  apiType: 'posts',
  filterTarget: 'post',
  icon: 'far fa-comment',
  order: 20,
  buildResultItems(items, { query }) {
    return items.map(post => ({
      key: `post-${post.id}`,
      avatarAlt: post.user?.display_name || post.user?.username || '',
      avatarColor: getUserAvatarColor(post.user),
      avatarMode: true,
      avatarText: post.user?.avatar_url ? '' : getUserInitial(post.user),
      avatarUrl: post.user?.avatar_url || '',
      excerptHtml: buildSearchTextHtml(post.excerpt || post.content || '', query, 200),
      iconClass: 'far fa-comment',
      metaItems: [
        `#${post.number}`,
        post.user?.display_name || post.user?.username || '未知用户',
        formatRelativeTime(post.created_at),
      ],
      path: `/d/${post.discussion_id}?near=${post.number}`,
      titleHtml: buildSearchTextHtml(post.discussion_title || '帖子结果', query, 90),
      titleText: post.discussion_title || '帖子结果',
      userLayout: false,
    }))
  },
})

registerSearchSource({
  key: 'users',
  moduleId: 'users',
  type: 'users',
  label: '用户',
  routeType: 'users',
  apiType: 'users',
  filterTarget: '',
  icon: 'far fa-user',
  order: 30,
  buildResultItems(items, { query }) {
    return items.map(user => ({
      key: `user-${user.id}`,
      avatarAlt: user.username || '',
      avatarColor: getUserAvatarColor(user),
      avatarMode: true,
      avatarText: user.avatar_url ? '' : getUserInitial(user),
      avatarUrl: user.avatar_url || '',
      excerptHtml: buildSearchTextHtml(user.bio || `@${user.username}`, query, 150),
      iconClass: 'far fa-user',
      metaItems: [
        `@${user.username}`,
        `${user.discussion_count || 0} 讨论`,
        `${user.comment_count || 0} 回复`,
      ],
      path: buildUserPath(user),
      titleHtml: buildSearchTextHtml(user.display_name || user.username || '用户', query, 80),
      titleText: user.display_name || user.username || '用户',
      userLayout: true,
    }))
  },
})

registerUserBadge({
  key: 'staff',
  order: 10,
  isVisible: ({ user }) => Boolean(user?.is_staff),
  resolve: () => ({
    label: '管理员',
    className: 'badge-admin',
  }),
})

registerUserBadge({
  key: 'primary-group',
  moduleId: 'users',
  order: 20,
  isVisible: ({ user }) => Boolean(user?.primary_group?.name),
  resolve: ({ user }) => ({
    label: user.primary_group.name,
    icon: user.primary_group.icon || '',
    color: user.primary_group.color || '#4d698e',
    variant: 'group',
  }),
})

registerHeroMeta({
  key: 'profile-last-seen',
  moduleId: 'users',
  order: 10,
  surfaces: ['profile-hero'],
  resolve: ({ isOnline, formatLastSeen, user }) => ({
    icon: 'fas fa-circle',
    iconClassName: isOnline ? 'hero-meta-icon hero-meta-icon--online' : 'hero-meta-icon',
    text: isOnline ? '在线' : formatLastSeen(user?.last_seen_at),
  }),
})

registerHeroMeta({
  key: 'profile-joined-at',
  moduleId: 'users',
  order: 20,
  surfaces: ['profile-hero'],
  isVisible: ({ user }) => Boolean(user?.joined_at),
  resolve: ({ formatJoinDate, user }) => ({
    icon: 'fas fa-clock',
    text: `加入于 ${formatJoinDate(user.joined_at)}`,
    title: user.joined_at,
  }),
})

registerDiscussionBadge({
  key: 'sticky',
  moduleId: 'discussions',
  order: 10,
  isVisible: ({ discussion }) => Boolean(discussion?.is_sticky),
  resolve: () => ({
    className: 'badge-pinned',
    icon: 'fas fa-thumbtack',
    title: '置顶',
  }),
})

registerDiscussionBadge({
  key: 'locked',
  moduleId: 'discussions',
  order: 20,
  isVisible: ({ discussion }) => Boolean(discussion?.is_locked),
  resolve: () => ({
    className: 'badge-locked',
    icon: 'fas fa-lock',
    title: '锁定',
  }),
})

registerDiscussionBadge({
  key: 'hidden',
  moduleId: 'discussions',
  order: 30,
  surfaces: ['hero'],
  isVisible: ({ discussion }) => Boolean(discussion?.is_hidden),
  resolve: () => ({
    className: 'badge-hidden',
    label: '隐藏',
  }),
})

registerHeroMeta({
  key: 'discussion-author',
  moduleId: 'discussions',
  order: 10,
  surfaces: ['discussion-hero'],
  isVisible: ({ discussion }) => Boolean(discussion?.user),
  resolve: ({ discussion }) => ({
    icon: 'far fa-user',
    text: discussion.user?.display_name || discussion.user?.username || '未知用户',
    to: buildUserPath(discussion.user),
  }),
})

registerHeroMeta({
  key: 'discussion-created-at',
  moduleId: 'discussions',
  order: 20,
  surfaces: ['discussion-hero'],
  isVisible: ({ discussion }) => Boolean(discussion?.created_at),
  resolve: ({ discussion }) => ({
    icon: 'far fa-clock',
    text: `发布于 ${formatRelativeTime(discussion.created_at)}`,
    title: discussion.created_at,
  }),
})

registerHeroMeta({
  key: 'discussion-last-posted-at',
  moduleId: 'discussions',
  order: 30,
  surfaces: ['discussion-hero'],
  isVisible: ({ discussion }) => Boolean(discussion?.last_posted_at),
  resolve: ({ discussion }) => ({
    icon: 'fas fa-reply',
    text: `最后回复 ${formatRelativeTime(discussion.last_posted_at)}`,
    title: discussion.last_posted_at,
  }),
})

registerHeroMeta({
  key: 'discussion-comment-count',
  moduleId: 'posts',
  order: 40,
  surfaces: ['discussion-hero'],
  isVisible: ({ discussion }) => Number(discussion?.comment_count || 0) > 0,
  resolve: ({ discussion }) => ({
    icon: 'far fa-comment',
    text: `${discussion.comment_count} 条回复`,
  }),
})

registerDiscussionStateBadge({
  key: 'unread',
  order: 30,
  surfaces: ['discussion-list-item'],
  isVisible: ({ discussion }) => Boolean(discussion?.is_unread && Number(discussion?.unread_count || 0) > 0),
  resolve: ({ discussion }) => ({
    label: `${discussion.unread_count} 条未读`,
    tone: 'primary',
  }),
})

registerDiscussionReplyState({
  key: 'suspended',
  order: 10,
  surfaces: ['discussion-reply'],
  isVisible: ({ authStore, isSuspended }) => Boolean(authStore?.isAuthenticated && isSuspended),
  resolve: ({ suspensionNotice }) => ({
    kind: 'notice',
    tone: 'warning',
    message: suspensionNotice,
  }),
})

registerDiscussionReplyState({
  key: 'composer',
  order: 20,
  surfaces: ['discussion-reply'],
  isVisible: ({ authStore, discussion }) => Boolean(authStore?.isAuthenticated && discussion?.can_reply),
  resolve: ({ hasActiveComposer }) => ({
    kind: 'composer',
    actionLabel: hasActiveComposer ? '继续编辑回复' : '发表回复',
    hint: hasActiveComposer ? '已有未发布内容' : '',
  }),
})

registerDiscussionReplyState({
  key: 'locked',
  order: 30,
  surfaces: ['discussion-reply'],
  isVisible: ({ discussion }) => Boolean(discussion?.is_locked),
  resolve: () => ({
    kind: 'notice',
    tone: 'warning',
    message: '此讨论已被锁定，无法回复',
  }),
})

registerDiscussionReplyState({
  key: 'no-permission',
  order: 60,
  surfaces: ['discussion-reply'],
  isVisible: ({ authStore }) => Boolean(authStore?.isAuthenticated),
  resolve: () => ({
    kind: 'notice',
    tone: 'warning',
    message: '当前没有在此讨论下回复的权限',
  }),
})

registerDiscussionReplyState({
  key: 'guest',
  order: 70,
  surfaces: ['discussion-reply'],
  resolve: () => ({
    kind: 'login',
    tone: 'warning',
    message: '后才能回复',
    linkLabel: '登录',
    to: '/login',
  }),
})

registerEmptyState({
  key: 'profile-discussions-empty',
  order: 10,
  surfaces: ['profile-discussion-empty'],
  isVisible: ({ discussions }) => Array.isArray(discussions) && discussions.length === 0,
  resolve: ({ isOwnProfile }) => ({
    text: isOwnProfile ? '你还没有发起过讨论' : '该用户还没有发起过讨论',
  }),
})

registerEmptyState({
  key: 'profile-posts-empty',
  order: 20,
  surfaces: ['profile-post-empty'],
  isVisible: ({ posts }) => Array.isArray(posts) && posts.length === 0,
  resolve: ({ isOwnProfile }) => ({
    text: isOwnProfile ? '你还没有发表过回复' : '该用户还没有发表过回复',
  }),
})

registerEmptyState({
  key: 'discussion-list-my-empty',
  order: 20,
  surfaces: ['discussion-list-empty'],
  isVisible: ({ listFilter }) => listFilter === 'my',
  resolve: () => ({
    text: '你还没有发起任何讨论。',
  }),
})

registerEmptyState({
  key: 'discussion-list-unread-empty',
  order: 30,
  surfaces: ['discussion-list-empty'],
  isVisible: ({ listFilter }) => listFilter === 'unread',
  resolve: () => ({
    text: '当前没有未读讨论。',
  }),
})

registerEmptyState({
  key: 'discussion-list-tag-empty',
  order: 40,
  surfaces: ['discussion-list-empty'],
  isVisible: ({ currentTag }) => Boolean(currentTag),
  resolve: () => ({
    text: '这个标签下还没有讨论。',
  }),
})

registerEmptyState({
  key: 'discussion-list-default-empty',
  order: 50,
  surfaces: ['discussion-list-empty'],
  isVisible: () => true,
  resolve: () => ({
    text: '暂无讨论。',
  }),
})

registerEmptyState({
  key: 'search-page-idle',
  order: 70,
  surfaces: ['search-page-idle'],
  isVisible: ({ hasQuery }) => !hasQuery,
  resolve: () => ({
    text: '请输入关键词后再搜索。',
  }),
})

registerEmptyState({
  key: 'search-page-empty',
  order: 80,
  surfaces: ['search-page-empty'],
  isVisible: ({ hasQuery }) => Boolean(hasQuery),
  resolve: () => ({
    text: '没有找到相关讨论、帖子或用户。',
  }),
})

registerEmptyState({
  key: 'search-modal-idle',
  order: 90,
  surfaces: ['search-modal-idle'],
  isVisible: ({ hasQuery }) => !hasQuery,
  resolve: () => ({
    text: '输入关键词后即可开始搜索。你可以直接回车进入完整搜索结果页。',
  }),
})

registerEmptyState({
  key: 'search-modal-empty',
  order: 100,
  surfaces: ['search-modal-empty'],
  isVisible: ({ hasQuery }) => Boolean(hasQuery),
  resolve: () => ({
    text: '没有找到相关结果，试试更短的关键词或切换分类。',
  }),
})

registerPageState({
  key: 'discussion-detail-loading',
  order: 10,
  surfaces: ['discussion-detail-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '加载中...',
  }),
})

registerPageState({
  key: 'discussion-detail-not-found',
  order: 20,
  surfaces: ['discussion-detail-not-found'],
  isVisible: ({ loading, discussion }) => !loading && !discussion,
  resolve: () => ({
    text: '讨论不存在',
  }),
})

registerPageState({
  key: 'profile-loading',
  order: 30,
  surfaces: ['profile-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '加载中...',
  }),
})

registerPageState({
  key: 'profile-not-found',
  order: 40,
  surfaces: ['profile-not-found'],
  isVisible: ({ loading, user }) => !loading && !user,
  resolve: () => ({
    text: '用户不存在',
  }),
})

registerStateBlock({
  key: 'discussion-list-loading',
  order: 10,
  surfaces: ['discussion-list-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '正在加载讨论...',
  }),
})

registerStateBlock({
  key: 'search-page-loading',
  order: 50,
  surfaces: ['search-page-loading'],
  isVisible: ({ loading, hasQuery }) => Boolean(loading) && Boolean(hasQuery),
  resolve: () => ({
    text: '搜索中...',
  }),
})

registerStateBlock({
  key: 'search-modal-loading',
  order: 60,
  surfaces: ['search-modal-loading'],
  isVisible: ({ loading, hasQuery }) => Boolean(loading) && Boolean(hasQuery),
  resolve: () => ({
    text: '搜索中...',
  }),
})

registerStateBlock({
  key: 'profile-discussion-loading',
  order: 70,
  surfaces: ['profile-discussion-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '加载中...',
  }),
})

registerStateBlock({
  key: 'profile-post-loading',
  order: 80,
  surfaces: ['profile-post-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '加载中...',
  }),
})

registerStateBlock({
  key: 'profile-preferences-loading',
  order: 90,
  surfaces: ['profile-preferences-loading'],
  isVisible: ({ loading }) => Boolean(loading),
  resolve: () => ({
    text: '加载偏好中...',
  }),
})

registerUiCopy({
  key: 'discussion-create-title',
  order: 10,
  surfaces: ['discussion-create-title'],
  resolve: () => ({
    text: '正在打开讨论编辑器...',
  }),
})

registerUiCopy({
  key: 'discussion-create-description',
  order: 20,
  surfaces: ['discussion-create-description'],
  resolve: () => ({
    text: '系统会自动切换到浮层编辑器。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-primary-tag-placeholder',
  order: 30,
  surfaces: ['discussion-composer-primary-tag-placeholder'],
  resolve: ({ loadingTags, hasStartableTags }) => ({
    text: loadingTags ? '加载标签中...' : (hasStartableTags ? '选择主标签' : '暂无可发帖标签'),
  }),
})

registerUiCopy({
  key: 'discussion-composer-secondary-tag-placeholder',
  order: 40,
  surfaces: ['discussion-composer-secondary-tag-placeholder'],
  resolve: ({ hasSecondaryOptions }) => ({
    text: hasSecondaryOptions ? '选择次标签（可选）' : '无可用次标签',
  }),
})

registerUiCopy({
  key: 'composer-preview-loading',
  order: 50,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ previewLoading }) => Boolean(previewLoading),
  resolve: () => ({
    text: '同步中',
  }),
})

registerUiCopy({
  key: 'composer-preview-empty',
  order: 60,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ hasContent }) => !hasContent,
  resolve: () => ({
    text: '暂无内容',
  }),
})

registerUiCopy({
  key: 'composer-preview-ready',
  order: 70,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ previewLoading, hasContent }) => !previewLoading && Boolean(hasContent),
  resolve: () => ({
    text: '按论坛最终渲染效果预览',
  }),
})

registerUiCopy({
  key: 'turnstile-loading',
  order: 90,
  surfaces: ['auth-turnstile-status'],
  isVisible: ({ turnstileLoading }) => Boolean(turnstileLoading),
  resolve: () => ({
    text: '真人验证加载中...',
  }),
})

registerUiCopy({
  key: 'turnstile-required',
  order: 100,
  surfaces: ['auth-turnstile-status'],
  isVisible: ({ humanVerificationRequired, hasToken }) => Boolean(humanVerificationRequired) && !hasToken,
  resolve: () => ({
    text: '请完成真人验证后再继续。',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-loading',
  order: 110,
  surfaces: ['composer-preview-panel-loading'],
  resolve: () => ({
    text: '正在生成预览...',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-empty',
  order: 120,
  surfaces: ['composer-preview-panel-empty'],
  resolve: () => ({
    text: '输入内容后即可查看预览',
  }),
})

registerUiCopy({
  key: 'header-search-placeholder',
  order: 130,
  surfaces: ['header-search-placeholder'],
  resolve: () => ({
    text: '搜索论坛',
  }),
})

registerUiCopy({
  key: 'profile-settings-section-title',
  order: 135,
  surfaces: ['profile-settings-section-title'],
  resolve: () => ({
    text: '个人设置',
  }),
})

registerUiCopy({
  key: 'profile-settings-section-description',
  order: 136,
  surfaces: ['profile-settings-section-description'],
  resolve: () => ({
    text: '维护你的显示名称、邮箱、个人简介和通知偏好。',
  }),
})

registerUiCopy({
  key: 'profile-settings-display-name-label',
  order: 137,
  surfaces: ['profile-settings-display-name-label'],
  resolve: () => ({
    text: '显示名称',
  }),
})

registerUiCopy({
  key: 'profile-settings-email-label',
  order: 138,
  surfaces: ['profile-settings-email-label'],
  resolve: () => ({
    text: '邮箱',
  }),
})

registerUiCopy({
  key: 'profile-settings-bio-label',
  order: 139,
  surfaces: ['profile-settings-bio-label'],
  resolve: () => ({
    text: '个人简介',
  }),
})

registerUiCopy({
  key: 'profile-settings-display-name-placeholder',
  order: 140,
  surfaces: ['profile-settings-display-name-placeholder'],
  resolve: () => ({
    text: '显示名称',
  }),
})

registerUiCopy({
  key: 'profile-settings-email-placeholder',
  order: 150,
  surfaces: ['profile-settings-email-placeholder'],
  resolve: () => ({
    text: 'name@example.com',
  }),
})

registerUiCopy({
  key: 'profile-settings-bio-placeholder',
  order: 160,
  surfaces: ['profile-settings-bio-placeholder'],
  resolve: () => ({
    text: '介绍一下自己...',
  }),
})

registerUiCopy({
  key: 'profile-settings-email-help',
  order: 170,
  surfaces: ['profile-settings-email-help'],
  resolve: ({ isEmailConfirmed }) => ({
    text: isEmailConfirmed ? '当前邮箱已完成验证。' : '修改邮箱后会重新进入未验证状态。',
  }),
})

registerUiCopy({
  key: 'profile-security-section-title',
  order: 175,
  surfaces: ['profile-security-section-title'],
  resolve: () => ({
    text: '账号安全',
  }),
})

registerUiCopy({
  key: 'profile-security-section-description',
  order: 176,
  surfaces: ['profile-security-section-description'],
  resolve: () => ({
    text: '查看邮箱验证状态，并修改登录密码。',
  }),
})

registerUiCopy({
  key: 'profile-security-email-section-title',
  order: 177,
  surfaces: ['profile-security-email-section-title'],
  resolve: () => ({
    text: '邮箱验证',
  }),
})

registerUiCopy({
  key: 'profile-security-email-section-description',
  order: 178,
  surfaces: ['profile-security-email-section-description'],
  resolve: () => ({
    text: '验证邮箱后，可确保找回密码和安全通知正常送达。',
  }),
})

registerUiCopy({
  key: 'profile-security-status-label',
  order: 180,
  surfaces: ['profile-security-status-label'],
  resolve: ({ isEmailConfirmed }) => ({
    text: isEmailConfirmed ? '已验证' : '未验证',
  }),
})

registerUiCopy({
  key: 'profile-security-email-help',
  order: 190,
  surfaces: ['profile-security-email-help'],
  resolve: ({ isEmailConfirmed }) => ({
    text: isEmailConfirmed ? '当前邮箱已通过验证。' : '当前邮箱尚未验证，你可以重新发送验证邮件。',
  }),
})

registerUiCopy({
  key: 'profile-security-resend-button',
  order: 200,
  surfaces: ['profile-security-resend-button'],
  resolve: ({ sending }) => ({
    text: sending ? '发送中...' : '重新发送验证邮件',
  }),
})

registerUiCopy({
  key: 'profile-security-old-password-label',
  order: 207,
  surfaces: ['profile-security-old-password-label'],
  resolve: () => ({
    text: '当前密码',
  }),
})

registerUiCopy({
  key: 'profile-security-old-password-placeholder',
  order: 210,
  surfaces: ['profile-security-old-password-placeholder'],
  resolve: () => ({
    text: '请输入当前密码',
  }),
})

registerUiCopy({
  key: 'profile-security-new-password-label',
  order: 217,
  surfaces: ['profile-security-new-password-label'],
  resolve: () => ({
    text: '新密码',
  }),
})

registerUiCopy({
  key: 'profile-security-new-password-placeholder',
  order: 220,
  surfaces: ['profile-security-new-password-placeholder'],
  resolve: () => ({
    text: '请输入新密码',
  }),
})

registerUiCopy({
  key: 'profile-security-confirm-password-label',
  order: 227,
  surfaces: ['profile-security-confirm-password-label'],
  resolve: () => ({
    text: '确认新密码',
  }),
})

registerUiCopy({
  key: 'profile-security-confirm-password-placeholder',
  order: 230,
  surfaces: ['profile-security-confirm-password-placeholder'],
  resolve: () => ({
    text: '请再次输入新密码',
  }),
})

registerUiCopy({
  key: 'profile-security-password-section-title',
  order: 235,
  surfaces: ['profile-security-password-section-title'],
  resolve: () => ({
    text: '修改密码',
  }),
})

registerUiCopy({
  key: 'profile-security-password-section-description',
  order: 236,
  surfaces: ['profile-security-password-section-description'],
  resolve: () => ({
    text: '修改后，下次登录请使用新密码。',
  }),
})

registerUiCopy({
  key: 'profile-security-submit-button',
  order: 240,
  surfaces: ['profile-security-submit-button'],
  resolve: ({ submitting }) => ({
    text: submitting ? '提交中...' : '更新密码',
  }),
})

registerUiCopy({
  key: 'profile-settings-save-button',
  order: 250,
  surfaces: ['profile-settings-save-button'],
  resolve: ({ saving }) => ({
    text: saving ? '保存中...' : '保存资料',
  }),
})

registerUiCopy({
  key: 'profile-settings-save-success',
  order: 255,
  surfaces: ['profile-settings-save-success'],
  resolve: ({ emailChanged, email }) => ({
    text: emailChanged ? `资料已保存，验证邮件已发送到 ${email}` : '资料已保存',
  }),
})

registerUiCopy({
  key: 'profile-settings-save-error',
  order: 256,
  surfaces: ['profile-settings-save-error'],
  resolve: () => ({
    text: '保存失败',
  }),
})

registerUiCopy({
  key: 'profile-settings-load-error',
  order: 256,
  surfaces: ['profile-settings-load-error'],
  resolve: () => ({
    text: '加载用户失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'profile-discussions-load-error',
  order: 256,
  surfaces: ['profile-discussions-load-error'],
  resolve: () => ({
    text: '加载讨论失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'profile-posts-load-error',
  order: 256,
  surfaces: ['profile-posts-load-error'],
  resolve: () => ({
    text: '加载回复失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'profile-preferences-section-title',
  order: 257,
  surfaces: ['profile-preferences-section-title'],
  resolve: () => ({
    text: '通知偏好',
  }),
})

registerUiCopy({
  key: 'profile-preferences-section-description',
  order: 258,
  surfaces: ['profile-preferences-section-description'],
  resolve: () => ({
    text: '按模块统一管理自动关注和通知订阅，新增通知类型后可以直接从注册表接入这里。',
  }),
})

registerUiCopy({
  key: 'profile-preferences-group-label',
  order: 259,
  surfaces: ['profile-preferences-group-label'],
  resolve: ({ category }) => ({
    text: category === 'behavior' ? '自动关注' : '通知订阅',
  }),
})

registerUiCopy({
  key: 'profile-preferences-group-description',
  order: 259,
  surfaces: ['profile-preferences-group-description'],
  resolve: ({ category }) => ({
    text: category === 'behavior'
      ? '控制发帖和回帖时的默认关注行为。'
      : '控制哪些站内通知会推送给你。',
  }),
})

registerUiCopy({
  key: 'profile-preferences-save-button',
  order: 260,
  surfaces: ['profile-preferences-save-button'],
  resolve: ({ saving }) => ({
    text: saving ? '保存中...' : '保存偏好',
  }),
})

registerUiCopy({
  key: 'profile-preferences-load-error',
  order: 261,
  surfaces: ['profile-preferences-load-error'],
  resolve: () => ({
    text: '加载通知偏好失败',
  }),
})

registerUiCopy({
  key: 'profile-preferences-save-success',
  order: 262,
  surfaces: ['profile-preferences-save-success'],
  resolve: () => ({
    text: '通知偏好已保存',
  }),
})

registerUiCopy({
  key: 'profile-preferences-save-error',
  order: 263,
  surfaces: ['profile-preferences-save-error'],
  resolve: () => ({
    text: '保存通知偏好失败',
  }),
})

registerUiCopy({
  key: 'profile-verification-success',
  order: 264,
  surfaces: ['profile-verification-success'],
  resolve: () => ({
    text: '验证邮件已发送',
  }),
})

registerUiCopy({
  key: 'profile-verification-error',
  order: 265,
  surfaces: ['profile-verification-error'],
  resolve: () => ({
    text: '发送失败',
  }),
})

registerUiCopy({
  key: 'profile-password-empty-error',
  order: 266,
  surfaces: ['profile-password-empty-error'],
  resolve: () => ({
    text: '请完整填写密码信息',
  }),
})

registerUiCopy({
  key: 'profile-password-mismatch-error',
  order: 267,
  surfaces: ['profile-password-mismatch-error'],
  resolve: () => ({
    text: '两次输入的新密码不一致',
  }),
})

registerUiCopy({
  key: 'profile-password-success',
  order: 268,
  surfaces: ['profile-password-success'],
  resolve: () => ({
    text: '密码修改成功',
  }),
})

registerUiCopy({
  key: 'profile-password-error',
  order: 269,
  surfaces: ['profile-password-error'],
  resolve: () => ({
    text: '密码修改失败',
  }),
})

registerUiCopy({
  key: 'auth-login-identification-placeholder',
  order: 270,
  surfaces: ['auth-login-identification-placeholder'],
  resolve: () => ({
    text: '请输入用户名或邮箱',
  }),
})

registerUiCopy({
  key: 'auth-login-password-placeholder',
  order: 280,
  surfaces: ['auth-login-password-placeholder'],
  resolve: () => ({
    text: '请输入密码',
  }),
})

registerUiCopy({
  key: 'auth-register-username-placeholder',
  order: 290,
  surfaces: ['auth-register-username-placeholder'],
  resolve: () => ({
    text: '3-30 个字符',
  }),
})

registerUiCopy({
  key: 'auth-register-email-placeholder',
  order: 300,
  surfaces: ['auth-register-email-placeholder'],
  resolve: () => ({
    text: '请输入邮箱',
  }),
})

registerUiCopy({
  key: 'auth-register-password-placeholder',
  order: 310,
  surfaces: ['auth-register-password-placeholder'],
  resolve: () => ({
    text: '至少 6 个字符',
  }),
})

registerUiCopy({
  key: 'auth-register-password-confirm-placeholder',
  order: 320,
  surfaces: ['auth-register-password-confirm-placeholder'],
  resolve: () => ({
    text: '请再次输入密码',
  }),
})

registerUiCopy({
  key: 'auth-forgot-email-placeholder',
  order: 330,
  surfaces: ['auth-forgot-email-placeholder'],
  resolve: () => ({
    text: '请输入注册邮箱',
  }),
})

registerUiCopy({
  key: 'auth-forgot-success',
  order: 340,
  surfaces: ['auth-forgot-success'],
  resolve: () => ({
    text: '重置链接已发送，请检查邮箱。',
  }),
})

registerUiCopy({
  key: 'auth-debug-reset-title',
  order: 350,
  surfaces: ['auth-debug-reset-title'],
  resolve: () => ({
    text: '开发环境调试链接',
  }),
})

registerUiCopy({
  key: 'auth-login-submit',
  order: 360,
  surfaces: ['auth-login-submit'],
  resolve: ({ loading }) => ({
    text: loading ? '登录中...' : '登录',
  }),
})

registerUiCopy({
  key: 'auth-register-submit',
  order: 370,
  surfaces: ['auth-register-submit'],
  resolve: ({ loading }) => ({
    text: loading ? '注册中...' : '注册',
  }),
})

registerUiCopy({
  key: 'auth-forgot-submit',
  order: 380,
  surfaces: ['auth-forgot-submit'],
  resolve: ({ loading }) => ({
    text: loading ? '发送中...' : '发送重置链接',
  }),
})

registerUiCopy({
  key: 'reset-password-token-placeholder',
  order: 390,
  surfaces: ['reset-password-token-placeholder'],
  resolve: () => ({
    text: '请输入邮件中的重置令牌',
  }),
})

registerUiCopy({
  key: 'reset-password-new-placeholder',
  order: 400,
  surfaces: ['reset-password-new-placeholder'],
  resolve: () => ({
    text: '请输入新密码',
  }),
})

registerUiCopy({
  key: 'reset-password-confirm-placeholder',
  order: 410,
  surfaces: ['reset-password-confirm-placeholder'],
  resolve: () => ({
    text: '请再次输入新密码',
  }),
})

registerUiCopy({
  key: 'reset-password-submit',
  order: 420,
  surfaces: ['reset-password-submit'],
  resolve: ({ loading }) => ({
    text: loading ? '提交中...' : '重置密码',
  }),
})

registerUiCopy({
  key: 'search-modal-close-label',
  order: 430,
  surfaces: ['search-modal-close-label'],
  resolve: () => ({
    text: '关闭搜索',
  }),
})

registerUiCopy({
  key: 'search-modal-title',
  order: 440,
  surfaces: ['search-modal-title'],
  resolve: () => ({
    text: '搜索',
  }),
})

registerUiCopy({
  key: 'search-modal-description',
  order: 450,
  surfaces: ['search-modal-description'],
  resolve: () => ({
    text: '按讨论、帖子、用户快速定位内容。',
  }),
})

registerUiCopy({
  key: 'search-modal-input-placeholder',
  order: 460,
  surfaces: ['search-modal-input-placeholder'],
  resolve: () => ({
    text: '输入关键词搜索讨论、帖子和用户',
  }),
})

registerUiCopy({
  key: 'search-modal-full-results',
  order: 470,
  surfaces: ['search-modal-full-results'],
  resolve: ({ activeTabLabel }) => ({
    text: `查看${activeTabLabel || '全部'}完整结果`,
  }),
})

registerUiCopy({
  key: 'search-modal-section-link',
  order: 475,
  surfaces: ['search-modal-section-link'],
  resolve: () => ({
    text: '只看{label}',
  }),
})

registerUiCopy({
  key: 'search-modal-recent-title',
  order: 476,
  surfaces: ['search-modal-recent-title'],
  resolve: () => ({
    text: '最近搜索',
  }),
})

registerUiCopy({
  key: 'search-modal-recent-subtitle',
  order: 476,
  surfaces: ['search-modal-recent-subtitle'],
  resolve: ({ activeTabLabel }) => ({
    text: `只看${activeTabLabel || '当前分类'}`,
  }),
})

registerUiCopy({
  key: 'search-modal-recent-all-subtitle',
  order: 476,
  surfaces: ['search-modal-recent-all-subtitle'],
  resolve: () => ({
    text: '搜索全部内容',
  }),
})

registerUiCopy({
  key: 'search-modal-syntax-title',
  order: 476,
  surfaces: ['search-modal-syntax-title'],
  resolve: () => ({
    text: '搜索语法',
  }),
})

registerUiCopy({
  key: 'search-page-hero-pill',
  order: 478,
  surfaces: ['search-page-hero-pill'],
  resolve: () => ({
    text: '全局搜索',
  }),
})

registerUiCopy({
  key: 'search-page-hero-title',
  order: 479,
  surfaces: ['search-page-hero-title'],
  resolve: ({ query }) => ({
    text: `“${query || '未输入关键词'}”`,
  }),
})

registerUiCopy({
  key: 'search-page-hero-description',
  order: 479,
  surfaces: ['search-page-hero-description'],
  resolve: ({ hasQuery, searchType, total, discussionTotal, postTotal, userTotal, activeLabel }) => {
    if (!hasQuery) {
      return {
        text: '支持在讨论、帖子和用户之间进行全局搜索。',
      }
    }

    if (searchType === 'all') {
      return {
        text: `共找到 ${discussionTotal + postTotal + userTotal} 条结果，已按讨论、帖子和用户分组展示。`,
      }
    }

    return {
      text: `当前显示 ${activeLabel || '结果'}结果，共 ${total || 0} 条。`,
    }
  },
})

registerUiCopy({
  key: 'search-page-meta-title',
  order: 479,
  surfaces: ['search-page-meta-title'],
  resolve: ({ query }) => ({
    text: query ? `搜索：${query}` : '搜索',
  }),
})

registerUiCopy({
  key: 'search-page-meta-description',
  order: 479,
  surfaces: ['search-page-meta-description'],
  resolve: ({ query, hasQuery }) => ({
    text: hasQuery ? `查看“${query}”相关的讨论、回复和用户结果。` : '搜索论坛中的讨论、回复和用户。',
  }),
})

registerUiCopy({
  key: 'search-result-section-show-more',
  order: 479,
  surfaces: ['search-result-section-show-more'],
  resolve: () => ({
    text: '查看全部',
  }),
})

registerUiCopy({
  key: 'search-page-stats-label',
  order: 479,
  surfaces: ['search-page-stats-label'],
  resolve: ({ itemKey }) => ({
    text: itemKey === 'posts' ? '帖子' : itemKey === 'users' ? '用户' : '讨论',
  }),
})

registerUiCopy({
  key: 'search-section-discussions-title',
  order: 479,
  surfaces: ['search-section-discussions-title'],
  resolve: () => ({
    text: '讨论',
  }),
})

registerUiCopy({
  key: 'search-discussion-result-replies',
  order: 479,
  surfaces: ['search-discussion-result-replies'],
  resolve: ({ count }) => ({
    text: `${count || 0} 回复`,
  }),
})

registerUiCopy({
  key: 'search-section-posts-title',
  order: 479,
  surfaces: ['search-section-posts-title'],
  resolve: () => ({
    text: '帖子',
  }),
})

registerUiCopy({
  key: 'search-result-unknown-user',
  order: 479,
  surfaces: ['search-result-unknown-user'],
  resolve: () => ({
    text: '未知用户',
  }),
})

registerUiCopy({
  key: 'search-section-users-title',
  order: 479,
  surfaces: ['search-section-users-title'],
  resolve: () => ({
    text: '用户',
  }),
})

registerUiCopy({
  key: 'search-user-result-discussions',
  order: 479,
  surfaces: ['search-user-result-discussions'],
  resolve: ({ count }) => ({
    text: `${count || 0} 讨论`,
  }),
})

registerUiCopy({
  key: 'search-user-result-replies',
  order: 479,
  surfaces: ['search-user-result-replies'],
  resolve: ({ count }) => ({
    text: `${count || 0} 回复`,
  }),
})

registerUiCopy({
  key: 'home-hero-title',
  order: 479,
  surfaces: ['home-hero-title'],
  resolve: () => ({
    text: 'Bias',
  }),
})

registerUiCopy({
  key: 'home-hero-description',
  order: 479,
  surfaces: ['home-hero-description'],
  resolve: () => ({
    text: '基于 Django 和 Vue 3 的现代化论坛',
  }),
})

registerUiCopy({
  key: 'home-browse-discussions',
  order: 479,
  surfaces: ['home-browse-discussions'],
  resolve: () => ({
    text: '浏览讨论',
  }),
})

registerUiCopy({
  key: 'home-start-discussion',
  order: 479,
  surfaces: ['home-start-discussion'],
  resolve: () => ({
    text: '发起讨论',
  }),
})

registerUiCopy({
  key: 'home-register-account',
  order: 479,
  surfaces: ['home-register-account'],
  resolve: () => ({
    text: '注册账号',
  }),
})

registerUiCopy({
  key: 'start-discussion-button',
  order: 479,
  surfaces: ['start-discussion-button'],
  resolve: ({ hasTag, tagName }) => ({
    text: hasTag && tagName ? `在 ${tagName} 下发起讨论` : '发起讨论',
  }),
})

registerUiCopy({
  key: 'search-filter-all-label',
  order: 479,
  surfaces: ['search-filter-all-label'],
  resolve: () => ({
    text: '全部',
  }),
})

registerUiCopy({
  key: 'search-filter-item-label',
  order: 479,
  surfaces: ['search-filter-item-label'],
  resolve: ({ label }) => ({
    text: label || '',
  }),
})

registerUiCopy({
  key: 'search-stat-label',
  order: 479,
  surfaces: ['search-stat-label'],
  resolve: ({ label }) => ({
    text: label || '',
  }),
})

registerUiCopy({
  key: 'search-filter-catalog-load-error',
  order: 479,
  surfaces: ['search-filter-catalog-load-error'],
  resolve: () => ({
    text: '加载搜索过滤目录失败',
  }),
})

registerUiCopy({
  key: 'search-results-load-error',
  order: 479,
  surfaces: ['search-results-load-error'],
  resolve: () => ({
    text: '加载搜索结果失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'search-results-total-count',
  order: 479,
  surfaces: ['search-results-total-count'],
  resolve: ({ count }) => ({
    text: String(Number(count || 0)),
  }),
})

registerUiCopy({
  key: 'search-results-source-count',
  order: 479,
  surfaces: ['search-results-source-count'],
  resolve: ({ count }) => ({
    text: String(Number(count || 0)),
  }),
})

registerUiCopy({
  key: 'discussion-action-confirm-cancel',
  order: 479,
  surfaces: ['discussion-action-confirm-cancel'],
  resolve: () => ({
    text: '取消',
  }),
})

registerUiCopy({
  key: 'discussion-action-confirm-default',
  order: 479,
  surfaces: ['discussion-action-confirm-default'],
  resolve: () => ({
    text: '继续',
  }),
})

registerUiCopy({
  key: 'discussion-action-reply-label',
  order: 479,
  surfaces: ['discussion-action-reply-label'],
  resolve: ({ hasActiveComposer }) => ({
    text: hasActiveComposer ? '继续回复' : '回复讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-reply-description',
  order: 479,
  surfaces: ['discussion-action-reply-description'],
  resolve: ({ hasActiveComposer }) => ({
    text: hasActiveComposer ? '继续当前未发布的回复草稿。' : '在当前讨论中开始撰写回复。',
  }),
})

registerUiCopy({
  key: 'discussion-action-login-label',
  order: 479,
  surfaces: ['discussion-action-login-label'],
  resolve: () => ({
    text: '登录后回复',
  }),
})

registerUiCopy({
  key: 'discussion-action-login-description',
  order: 479,
  surfaces: ['discussion-action-login-description'],
  resolve: () => ({
    text: '登录后才可以参与当前讨论。',
  }),
})

registerUiCopy({
  key: 'discussion-action-edit-label',
  order: 479,
  surfaces: ['discussion-action-edit-label'],
  resolve: () => ({
    text: '编辑讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-edit-description',
  order: 479,
  surfaces: ['discussion-action-edit-description'],
  resolve: () => ({
    text: '修改标题、正文和标签。',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-pin-label',
  order: 479,
  surfaces: ['discussion-action-toggle-pin-label'],
  resolve: ({ isSticky }) => ({
    text: isSticky ? '取消置顶' : '置顶讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-pin-description',
  order: 479,
  surfaces: ['discussion-action-toggle-pin-description'],
  resolve: ({ isSticky }) => ({
    text: isSticky ? '把讨论恢复为普通排序。' : '把讨论固定到列表更靠前的位置。',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-pin-confirm-title',
  order: 479,
  surfaces: ['discussion-action-toggle-pin-confirm-title'],
  resolve: () => ({
    text: '置顶讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-pin-confirm-message',
  order: 479,
  surfaces: ['discussion-action-toggle-pin-confirm-message'],
  resolve: () => ({
    text: '确定将这条讨论置顶吗？',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-pin-confirm-confirm',
  order: 479,
  surfaces: ['discussion-action-toggle-pin-confirm-confirm'],
  resolve: () => ({
    text: '置顶讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-lock-label',
  order: 479,
  surfaces: ['discussion-action-toggle-lock-label'],
  resolve: ({ isLocked }) => ({
    text: isLocked ? '解除锁定' : '锁定讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-lock-description',
  order: 479,
  surfaces: ['discussion-action-toggle-lock-description'],
  resolve: ({ isLocked }) => ({
    text: isLocked ? '恢复普通用户回复能力。' : '阻止普通用户继续回复。',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-lock-confirm-title',
  order: 479,
  surfaces: ['discussion-action-toggle-lock-confirm-title'],
  resolve: () => ({
    text: '锁定讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-lock-confirm-message',
  order: 479,
  surfaces: ['discussion-action-toggle-lock-confirm-message'],
  resolve: () => ({
    text: '确定锁定当前讨论并阻止普通用户继续回复吗？',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-lock-confirm-confirm',
  order: 479,
  surfaces: ['discussion-action-toggle-lock-confirm-confirm'],
  resolve: () => ({
    text: '锁定讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-hide-label',
  order: 479,
  surfaces: ['discussion-action-toggle-hide-label'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-hide-description',
  order: 479,
  surfaces: ['discussion-action-toggle-hide-description'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '重新让讨论出现在前台列表。' : '临时从前台列表隐藏当前讨论。',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-hide-confirm-title',
  order: 479,
  surfaces: ['discussion-action-toggle-hide-confirm-title'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-hide-confirm-message',
  order: 479,
  surfaces: ['discussion-action-toggle-hide-confirm-message'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '确定恢复显示当前讨论吗？' : '确定从前台列表隐藏当前讨论吗？',
  }),
})

registerUiCopy({
  key: 'discussion-action-toggle-hide-confirm-confirm',
  order: 479,
  surfaces: ['discussion-action-toggle-hide-confirm-confirm'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-delete-label',
  order: 479,
  surfaces: ['discussion-action-delete-label'],
  resolve: () => ({
    text: '删除讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-delete-description',
  order: 479,
  surfaces: ['discussion-action-delete-description'],
  resolve: () => ({
    text: '永久删除当前讨论及其回复。',
  }),
})

registerUiCopy({
  key: 'discussion-action-delete-confirm-title',
  order: 479,
  surfaces: ['discussion-action-delete-confirm-title'],
  resolve: () => ({
    text: '删除讨论',
  }),
})

registerUiCopy({
  key: 'discussion-action-delete-confirm-message',
  order: 479,
  surfaces: ['discussion-action-delete-confirm-message'],
  resolve: () => ({
    text: '确定要删除这个讨论吗？此操作不可恢复。',
  }),
})

registerUiCopy({
  key: 'discussion-action-delete-confirm-confirm',
  order: 479,
  surfaces: ['discussion-action-delete-confirm-confirm'],
  resolve: () => ({
    text: '删除',
  }),
})

registerUiCopy({
  key: 'post-action-edit-label',
  order: 479,
  surfaces: ['post-action-edit-label'],
  resolve: () => ({
    text: '编辑',
  }),
})

registerUiCopy({
  key: 'post-action-edit-description',
  order: 479,
  surfaces: ['post-action-edit-description'],
  resolve: () => ({
    text: '修改这条回复内容。',
  }),
})

registerUiCopy({
  key: 'post-action-delete-label',
  order: 479,
  surfaces: ['post-action-delete-label'],
  resolve: () => ({
    text: '删除',
  }),
})

registerUiCopy({
  key: 'post-action-delete-description',
  order: 479,
  surfaces: ['post-action-delete-description'],
  resolve: () => ({
    text: '永久删除这条回复。',
  }),
})

registerUiCopy({
  key: 'post-action-delete-confirm-title',
  order: 479,
  surfaces: ['post-action-delete-confirm-title'],
  resolve: () => ({
    text: '删除回复',
  }),
})

registerUiCopy({
  key: 'post-action-delete-confirm-message',
  order: 479,
  surfaces: ['post-action-delete-confirm-message'],
  resolve: () => ({
    text: '确定要删除这条回复吗？此操作不可恢复。',
  }),
})

registerUiCopy({
  key: 'post-action-delete-confirm-confirm',
  order: 479,
  surfaces: ['post-action-delete-confirm-confirm'],
  resolve: () => ({
    text: '删除',
  }),
})

registerUiCopy({
  key: 'post-action-toggle-hide-label',
  order: 479,
  surfaces: ['post-action-toggle-hide-label'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏回复',
  }),
})

registerUiCopy({
  key: 'post-action-toggle-hide-description',
  order: 479,
  surfaces: ['post-action-toggle-hide-description'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '重新让这条回复在前台可见。' : '临时从前台隐藏这条回复。',
  }),
})

registerUiCopy({
  key: 'post-action-toggle-hide-confirm-title',
  order: 479,
  surfaces: ['post-action-toggle-hide-confirm-title'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏回复',
  }),
})

registerUiCopy({
  key: 'post-action-toggle-hide-confirm-message',
  order: 479,
  surfaces: ['post-action-toggle-hide-confirm-message'],
  resolve: ({ isHidden, postNumber }) => ({
    text: isHidden ? `确定恢复显示 #${postNumber} 吗？` : `确定隐藏 #${postNumber} 吗？`,
  }),
})

registerUiCopy({
  key: 'post-action-toggle-hide-confirm-confirm',
  order: 479,
  surfaces: ['post-action-toggle-hide-confirm-confirm'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '恢复显示' : '隐藏回复',
  }),
})

registerUiCopy({
  key: 'discussion-sidebar-active-draft',
  order: 479,
  surfaces: ['discussion-sidebar-active-draft'],
  resolve: () => ({
    text: '当前讨论已有未发布回复草稿。',
  }),
})

registerUiCopy({
  key: 'discussion-sidebar-locked',
  order: 479,
  surfaces: ['discussion-sidebar-locked'],
  resolve: () => ({
    text: '当前讨论已锁定，暂时无法继续回复。',
  }),
})

registerUiCopy({
  key: 'discussion-sidebar-suspension-title',
  order: 479,
  surfaces: ['discussion-sidebar-suspension-title'],
  resolve: () => ({
    text: '账号状态',
  }),
})

registerUiCopy({
  key: 'discussion-sidebar-scrubber-start',
  order: 479,
  surfaces: ['discussion-sidebar-scrubber-start'],
  resolve: () => ({
    text: '原帖',
  }),
})

registerUiCopy({
  key: 'discussion-sidebar-scrubber-end',
  order: 479,
  surfaces: ['discussion-sidebar-scrubber-end'],
  resolve: () => ({
    text: '现在',
  }),
})

registerUiCopy({
  key: 'discussion-detail-suspension-alert-title',
  order: 479,
  surfaces: ['discussion-detail-suspension-alert-title'],
  resolve: () => ({
    text: '账号已被封禁',
  }),
})

registerUiCopy({
  key: 'discussion-detail-suspension-notice',
  order: 479,
  surfaces: ['discussion-detail-suspension-notice'],
  resolve: ({ user, fallbackMessage, suspendedUntilText }) => {
    if (!user?.is_suspended) {
      return {
        text: '',
      }
    }

    if (user.suspend_message) {
      return {
        text: suspendedUntilText
          ? `账号已被封禁至 ${suspendedUntilText}。${user.suspend_message}`
          : `账号当前已被封禁。${user.suspend_message}`,
      }
    }

    return {
      text: suspendedUntilText
        ? `账号已被封禁至 ${suspendedUntilText}，${fallbackMessage}`
        : `账号当前已被封禁，${fallbackMessage}`,
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-action-error-title',
  order: 479,
  surfaces: ['discussion-detail-action-error-title'],
  resolve: ({ actionLabel }) => ({
    text: actionLabel ? `${actionLabel}失败` : '操作失败',
  }),
})

registerUiCopy({
  key: 'discussion-detail-action-retry-message',
  order: 479,
  surfaces: ['discussion-detail-action-retry-message'],
  resolve: () => ({
    text: '请稍后重试',
  }),
})

registerUiCopy({
  key: 'discussion-detail-moderation-title',
  order: 479,
  surfaces: ['discussion-detail-moderation-title'],
  resolve: ({ targetType, action, postNumber }) => {
    if (targetType === 'post') {
      return {
        text: action === 'approve' ? `审核通过 #${postNumber}` : `拒绝 #${postNumber}`,
      }
    }

    return {
      text: action === 'approve' ? '审核通过讨论' : '拒绝讨论',
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-moderation-description',
  order: 479,
  surfaces: ['discussion-detail-moderation-description'],
  resolve: ({ targetType, action }) => {
    if (targetType === 'post') {
      return {
        text: action === 'approve'
          ? '通过后，这条回复会立刻出现在讨论流中。'
          : '拒绝后，回复作者仍可在前台看到你的审核反馈。',
      }
    }

    return {
      text: action === 'approve'
        ? '通过后，这条讨论会立即对其他用户可见。'
        : '拒绝后，讨论作者仍可在前台看到你的审核反馈。',
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-moderation-confirm',
  order: 479,
  surfaces: ['discussion-detail-moderation-confirm'],
  resolve: ({ action }) => ({
    text: action === 'approve' ? '通过审核' : '确认拒绝',
  }),
})

registerUiCopy({
  key: 'discussion-detail-moderation-placeholder',
  order: 479,
  surfaces: ['discussion-detail-moderation-placeholder'],
  resolve: ({ targetType, action }) => {
    if (action === 'approve') {
      return {
        text: '例如：内容符合社区规范，已放行',
      }
    }

    return {
      text: targetType === 'post'
        ? '例如：回复缺少上下文，请补充后重新提交'
        : '例如：标题与正文需要补充后再发布',
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-moderation-success-title',
  order: 479,
  surfaces: ['discussion-detail-moderation-success-title'],
  resolve: ({ targetType, action }) => {
    if (targetType === 'post') {
      return {
        text: action === 'approve' ? '回复已通过' : '回复已拒绝',
      }
    }

    return {
      text: action === 'approve' ? '讨论已通过' : '讨论已拒绝',
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-moderation-success-message',
  order: 479,
  surfaces: ['discussion-detail-moderation-success-message'],
  resolve: ({ targetType, action }) => {
    if (targetType === 'post') {
      return {
        text: action === 'approve'
          ? '这条回复现在已经加入讨论流。'
          : '作者现在可以在前台看到你的审核反馈。',
      }
    }

    return {
      text: action === 'approve'
        ? '这条讨论现在已经对其他用户可见。'
        : '作者现在可以在前台看到你的审核反馈。',
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-like-summary',
  order: 479,
  surfaces: ['discussion-detail-like-summary'],
  resolve: ({ count, isLiked }) => {
    if (Number(count || 0) <= 0) {
      return {
        text: '',
      }
    }

    if (isLiked) {
      return {
        text: Number(count) === 1 ? '你赞了这条回复' : `你和其他 ${Number(count) - 1} 人赞了这条回复`,
      }
    }

    return {
      text: `${Number(count)} 人赞了这条回复`,
    }
  },
})

registerUiCopy({
  key: 'discussion-detail-unknown-time',
  order: 479,
  surfaces: ['discussion-detail-unknown-time'],
  resolve: () => ({
    text: '未知时间',
  }),
})

registerUiCopy({
  key: 'forum-action-menu-item-title',
  order: 479,
  surfaces: ['forum-action-menu-item-title'],
  resolve: ({ disabledReason }) => ({
    text: disabledReason || '',
  }),
})

registerUiCopy({
  key: 'header-mobile-page-title',
  order: 479,
  surfaces: ['header-mobile-page-title'],
  resolve: ({ routeName, forumTitle, listFilter }) => ({
    text: routeName === 'home'
      ? getDiscussionListFilterLabelText(listFilter)
      : routeName === 'following'
        ? getDiscussionListFilterLabelText('following')
        : ({
          tags: '标签',
          profile: '个人主页',
          'user-profile': '个人主页',
          notifications: '通知',
          search: '搜索结果',
          'discussion-detail': '讨论详情',
          login: '登录',
          register: '注册',
        })[routeName] || forumTitle || 'Bias',
  }),
})

registerUiCopy({
  key: 'header-mobile-left-action-label',
  order: 479,
  surfaces: ['header-mobile-left-action-label'],
  resolve: ({ leftAction }) => ({
    text: leftAction === 'back' ? '返回上一页' : '打开导航菜单',
  }),
})

registerUiCopy({
  key: 'discussion-list-sidebar-profile-link',
  order: 479,
  surfaces: ['discussion-list-sidebar-profile-link'],
  resolve: () => ({
    text: '我的主页',
  }),
})

registerUiCopy({
  key: 'header-mobile-right-action-label',
  order: 479,
  surfaces: ['header-mobile-right-action-label'],
  resolve: ({ actionType }) => ({
    text: actionType === 'discussion-menu'
      ? '讨论操作菜单'
      : actionType === 'login'
        ? '登录'
        : '发起讨论',
  }),
})

registerUiCopy({
  key: 'discussion-list-default-filter-label',
  order: 479,
  surfaces: ['discussion-list-default-filter-label'],
  resolve: ({ code }) => ({
    text: getDiscussionListFilterLabelText(code),
  }),
})

registerUiCopy({
  key: 'discussion-list-action-failed-title',
  order: 479,
  surfaces: ['discussion-list-action-failed-title'],
  resolve: ({ actionType }) => ({
    text: actionType === 'refresh'
      ? '刷新失败'
      : actionType === 'mark-all-read'
        ? '标记已读失败'
        : actionType === 'load-more'
          ? '加载更多失败'
          : '操作失败',
  }),
})

registerUiCopy({
  key: 'discussion-list-action-retry-message',
  order: 479,
  surfaces: ['discussion-list-action-retry-message'],
  resolve: () => ({
    text: '请稍后重试',
  }),
})

registerUiCopy({
  key: 'discussion-list-filter-hero-pill',
  order: 479,
  surfaces: ['discussion-list-filter-hero-pill'],
  resolve: ({ listFilter }) => ({
    text: getDiscussionListFilterLabelText(listFilter),
  }),
})

registerUiCopy({
  key: 'discussion-list-filter-hero-title',
  order: 479,
  surfaces: ['discussion-list-filter-hero-title'],
  resolve: ({ listFilter }) => ({
    text: getDiscussionListFilterHeroTitleText(listFilter),
  }),
})

registerUiCopy({
  key: 'discussion-list-filter-hero-description',
  order: 479,
  surfaces: ['discussion-list-filter-hero-description'],
  resolve: ({ listFilter }) => ({
    text: getDiscussionListFilterHeroDescriptionText(listFilter),
  }),
})

registerUiCopy({
  key: 'discussion-list-tag-hero-description',
  order: 479,
  surfaces: ['discussion-list-tag-hero-description'],
  resolve: () => ({
    text: '这个标签下的讨论会集中显示在这里。',
  }),
})

registerUiCopy({
  key: 'discussion-list-page-meta-title',
  order: 479,
  surfaces: ['discussion-list-page-meta-title'],
  resolve: ({ listFilter, currentTagName, searchQuery, hasSearchQuery }) => {
    return {
      text: resolveDiscussionListPageMetaTitle({
        filterCode: listFilter,
        currentTagName,
        searchQuery: hasSearchQuery ? searchQuery : '',
      }),
    }
  },
})

registerUiCopy({
  key: 'discussion-list-page-meta-description',
  order: 479,
  surfaces: ['discussion-list-page-meta-description'],
  resolve: ({ listFilter, currentTagName, currentTagDescription, searchQuery, hasSearchQuery }) => {
    return {
      text: resolveDiscussionListPageMetaDescription({
        filterCode: listFilter,
        currentTagName,
        currentTagDescription,
        searchQuery: hasSearchQuery ? searchQuery : '',
      }),
    }
  },
})

registerUiCopy({
  key: 'discussion-event-post-number-title',
  order: 479,
  surfaces: ['discussion-event-post-number-title'],
  resolve: ({ postNumber }) => ({
    text: `跳转到第 ${postNumber} 楼`,
  }),
})

registerUiCopy({
  key: 'discussion-event-target-post-number-title',
  order: 479,
  surfaces: ['discussion-event-target-post-number-title'],
  resolve: ({ targetPostNumber }) => ({
    text: `跳转到相关的第 ${targetPostNumber} 楼`,
  }),
})

registerUiCopy({
  key: 'discussion-event-note-prefix',
  order: 479,
  surfaces: ['discussion-event-note-prefix'],
  resolve: () => ({
    text: '理由：',
  }),
})

registerUiCopy({
  key: 'discussion-event-approved-label',
  order: 479,
  surfaces: ['discussion-event-approved-label'],
  resolve: () => ({
    text: '通过了该讨论的审核',
  }),
})

registerUiCopy({
  key: 'discussion-event-rejected-label',
  order: 479,
  surfaces: ['discussion-event-rejected-label'],
  resolve: () => ({
    text: '拒绝了该讨论的审核',
  }),
})

registerUiCopy({
  key: 'discussion-event-hidden-label',
  order: 479,
  surfaces: ['discussion-event-hidden-label'],
  resolve: ({ isHidden }) => ({
    text: isHidden ? '隐藏了该讨论' : '恢复显示该讨论',
  }),
})

registerUiCopy({
  key: 'discussion-event-locked-label',
  order: 479,
  surfaces: ['discussion-event-locked-label'],
  resolve: ({ isLocked }) => ({
    text: isLocked ? '锁定了该讨论' : '解锁了该讨论',
  }),
})

registerUiCopy({
  key: 'discussion-event-resubmitted-label',
  order: 479,
  surfaces: ['discussion-event-resubmitted-label'],
  resolve: () => ({
    text: '修改后重新提交了该讨论的审核',
  }),
})

registerUiCopy({
  key: 'discussion-event-sticky-label',
  order: 479,
  surfaces: ['discussion-event-sticky-label'],
  resolve: ({ isSticky }) => ({
    text: isSticky ? '置顶了该讨论' : '取消了该讨论的置顶状态',
  }),
})

registerUiCopy({
  key: 'discussion-event-tagged-label',
  order: 479,
  surfaces: ['discussion-event-tagged-label'],
  resolve: () => ({
    text: '更新了讨论标签',
  }),
})

registerUiCopy({
  key: 'discussion-event-tagged-added-prefix',
  order: 479,
  surfaces: ['discussion-event-tagged-added-prefix'],
  resolve: () => ({
    text: '新增',
  }),
})

registerUiCopy({
  key: 'discussion-event-tagged-removed-prefix',
  order: 479,
  surfaces: ['discussion-event-tagged-removed-prefix'],
  resolve: () => ({
    text: '移除',
  }),
})

registerUiCopy({
  key: 'discussion-event-renamed-from-label',
  order: 479,
  surfaces: ['discussion-event-renamed-from-label'],
  resolve: () => ({
    text: '将讨论标题从',
  }),
})

registerUiCopy({
  key: 'discussion-event-renamed-to-label',
  order: 479,
  surfaces: ['discussion-event-renamed-to-label'],
  resolve: () => ({
    text: '改为',
  }),
})

registerUiCopy({
  key: 'discussion-event-renamed-old-title-fallback',
  order: 479,
  surfaces: ['discussion-event-renamed-old-title-fallback'],
  resolve: () => ({
    text: '旧标题',
  }),
})

registerUiCopy({
  key: 'discussion-event-renamed-new-title-fallback',
  order: 479,
  surfaces: ['discussion-event-renamed-new-title-fallback'],
  resolve: () => ({
    text: '新标题',
  }),
})

registerUiCopy({
  key: 'post-event-approved-label',
  order: 479,
  surfaces: ['post-event-approved-label'],
  resolve: ({ targetPostNumber }) => ({
    text: `通过了第 ${targetPostNumber} 楼回复的审核`,
  }),
})

registerUiCopy({
  key: 'post-event-rejected-label',
  order: 479,
  surfaces: ['post-event-rejected-label'],
  resolve: ({ targetPostNumber }) => ({
    text: `拒绝了第 ${targetPostNumber} 楼回复的审核`,
  }),
})

registerUiCopy({
  key: 'post-event-hidden-label',
  order: 479,
  surfaces: ['post-event-hidden-label'],
  resolve: ({ isHidden, targetPostNumber }) => ({
    text: isHidden ? `隐藏了第 ${targetPostNumber} 楼回复` : `恢复显示第 ${targetPostNumber} 楼回复`,
  }),
})

registerUiCopy({
  key: 'post-event-resubmitted-label',
  order: 479,
  surfaces: ['post-event-resubmitted-label'],
  resolve: ({ targetPostNumber }) => ({
    text: `修改后重新提交了第 ${targetPostNumber} 楼回复的审核`,
  }),
})

registerUiCopy({
  key: 'discussion-generic-event-fallback-label',
  order: 479,
  surfaces: ['discussion-generic-event-fallback-label'],
  resolve: () => ({
    text: '系统事件',
  }),
})

registerUiCopy({
  key: 'discussion-post-number-title',
  order: 479,
  surfaces: ['discussion-post-number-title'],
  resolve: ({ postNumber }) => ({
    text: `跳转到第 ${postNumber} 楼`,
  }),
})

registerUiCopy({
  key: 'discussion-post-edited-label',
  order: 479,
  surfaces: ['discussion-post-edited-label'],
  resolve: () => ({
    text: '已编辑',
  }),
})

registerUiCopy({
  key: 'discussion-post-like-action',
  order: 479,
  surfaces: ['discussion-post-like-action'],
  resolve: () => ({
    text: '赞',
  }),
})

registerUiCopy({
  key: 'discussion-post-reply-action',
  order: 479,
  surfaces: ['discussion-post-reply-action'],
  resolve: () => ({
    text: '回复',
  }),
})

registerUiCopy({
  key: 'discussion-list-item-created-at',
  order: 479,
  surfaces: ['discussion-list-item-created-at'],
  resolve: ({ relativeTime }) => ({
    text: `发起于 ${relativeTime}`,
  }),
})

registerUiCopy({
  key: 'discussion-list-item-last-posted-at',
  order: 479,
  surfaces: ['discussion-list-item-last-posted-at'],
  resolve: ({ relativeTime }) => ({
    text: `最后回复 ${relativeTime}`,
  }),
})

registerUiCopy({
  key: 'mobile-drawer-close-label',
  order: 480,
  surfaces: ['mobile-drawer-close-label'],
  resolve: () => ({
    text: '关闭导航菜单',
  }),
})

registerUiCopy({
  key: 'mobile-drawer-search-label',
  order: 490,
  surfaces: ['mobile-drawer-search-label'],
  resolve: ({ currentSearchQuery }) => ({
    text: currentSearchQuery ? `搜索：${currentSearchQuery}` : '搜索论坛',
  }),
})

registerUiCopy({
  key: 'mobile-drawer-start-discussion',
  order: 500,
  surfaces: ['mobile-drawer-start-discussion'],
  resolve: () => ({
    text: '发起讨论',
  }),
})

registerUiCopy({
  key: 'mobile-drawer-all-discussions',
  order: 510,
  surfaces: ['mobile-drawer-all-discussions'],
  resolve: () => ({
    text: '全部讨论',
  }),
})

registerUiCopy({
  key: 'mobile-drawer-profile-section-title',
  order: 540,
  surfaces: ['mobile-drawer-profile-section-title'],
  resolve: () => ({
    text: '个人',
  }),
})

registerUiCopy({
  key: 'discussion-composer-title-placeholder',
  order: 580,
  surfaces: ['discussion-composer-title-placeholder'],
  resolve: () => ({
    text: '讨论标题',
  }),
})

registerUiCopy({
  key: 'discussion-composer-content-placeholder',
  order: 590,
  surfaces: ['discussion-composer-content-placeholder'],
  resolve: () => ({
    text: '输入讨论内容... 支持 Markdown、@用户名 和代码块',
  }),
})

registerUiCopy({
  key: 'composer-preview-button-title',
  order: 600,
  surfaces: ['composer-preview-button-title'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'discussion-composer-submit',
  order: 610,
  surfaces: ['discussion-composer-submit'],
  resolve: ({ submitting, uploading, isEditingDiscussion }) => ({
    text: submitting
      ? (isEditingDiscussion ? '保存中...' : '发布中...')
      : (uploading ? '上传中...' : (isEditingDiscussion ? '保存讨论' : '发布讨论')),
  }),
})

registerUiCopy({
  key: 'discussion-composer-status-text',
  order: 611,
  surfaces: ['discussion-composer-status-text'],
  resolve: ({ hasDraftSavedAt, draftSavedAtText, isEditingDiscussion, selectedTagName }) => {
    if (hasDraftSavedAt) {
      return {
        text: `草稿保存于 ${draftSavedAtText}`,
      }
    }

    if (isEditingDiscussion) {
      return {
        text: '修改后可重新提交审核或直接更新讨论。',
      }
    }

    if (selectedTagName) {
      return {
        text: `将发布到 ${selectedTagName}`,
      }
    }

    return {
      text: '支持 Markdown，可最小化继续编辑。',
    }
  },
})

registerUiCopy({
  key: 'discussion-composer-minimized-summary',
  order: 612,
  surfaces: ['discussion-composer-minimized-summary'],
  resolve: ({ isEditingDiscussion, selectedTagName }) => ({
    text: isEditingDiscussion ? '编辑讨论' : (selectedTagName ? `新讨论 · ${selectedTagName}` : '发起讨论'),
  }),
})

registerUiCopy({
  key: 'discussion-composer-heading',
  order: 613,
  surfaces: ['discussion-composer-heading'],
  resolve: ({ isEditingDiscussion }) => ({
    text: isEditingDiscussion ? '编辑讨论' : '发起讨论',
  }),
})

registerUiCopy({
  key: 'discussion-composer-close-title',
  order: 614,
  surfaces: ['discussion-composer-close-title'],
  resolve: () => ({
    text: '关闭发帖编辑器',
  }),
})

registerUiCopy({
  key: 'discussion-composer-close-message',
  order: 615,
  surfaces: ['discussion-composer-close-message'],
  resolve: () => ({
    text: '确定要关闭发帖编辑器吗？当前内容会保留在本地草稿中。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-close-confirm',
  order: 616,
  surfaces: ['discussion-composer-close-confirm'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'discussion-composer-close-cancel',
  order: 617,
  surfaces: ['discussion-composer-close-cancel'],
  resolve: () => ({
    text: '继续编辑',
  }),
})

registerUiCopy({
  key: 'discussion-composer-draft-restored',
  order: 618,
  surfaces: ['discussion-composer-draft-restored'],
  resolve: ({ hasDraftSavedAt, draftSavedAtText }) => ({
    text: hasDraftSavedAt
      ? `已恢复你在 ${draftSavedAtText} 保存的讨论草稿。`
      : '已恢复本地讨论草稿。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-draft-restore-error',
  order: 619,
  surfaces: ['discussion-composer-draft-restore-error'],
  resolve: () => ({
    text: '讨论草稿恢复失败，已保留当前编辑内容。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-draft-emptied',
  order: 620,
  surfaces: ['discussion-composer-draft-emptied'],
  resolve: () => ({
    text: '草稿已清空',
  }),
})

registerUiCopy({
  key: 'discussion-composer-draft-saved',
  order: 621,
  surfaces: ['discussion-composer-draft-saved'],
  resolve: () => ({
    text: '讨论草稿已保存。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-clear-draft-title',
  order: 622,
  surfaces: ['discussion-composer-clear-draft-title'],
  resolve: () => ({
    text: '清除讨论草稿',
  }),
})

registerUiCopy({
  key: 'discussion-composer-clear-draft-message',
  order: 623,
  surfaces: ['discussion-composer-clear-draft-message'],
  resolve: () => ({
    text: '确定要清除当前讨论草稿吗？',
  }),
})

registerUiCopy({
  key: 'discussion-composer-clear-draft-confirm',
  order: 624,
  surfaces: ['discussion-composer-clear-draft-confirm'],
  resolve: () => ({
    text: '清除',
  }),
})

registerUiCopy({
  key: 'discussion-composer-clear-draft-cancel',
  order: 625,
  surfaces: ['discussion-composer-clear-draft-cancel'],
  resolve: () => ({
    text: '取消',
  }),
})

registerUiCopy({
  key: 'discussion-composer-draft-cleared-local',
  order: 626,
  surfaces: ['discussion-composer-draft-cleared-local'],
  resolve: () => ({
    text: '已清除本地草稿。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-unsaved-exit-message',
  order: 626,
  surfaces: ['discussion-composer-unsaved-exit-message'],
  resolve: () => ({
    text: '你有未发布的讨论内容。确定要离开当前页面吗？',
  }),
})

registerUiCopy({
  key: 'discussion-composer-edit-pending-title',
  order: 627,
  surfaces: ['discussion-composer-edit-pending-title'],
  resolve: () => ({
    text: '讨论已重新提交审核',
  }),
})

registerUiCopy({
  key: 'discussion-composer-edit-pending-message',
  order: 628,
  surfaces: ['discussion-composer-edit-pending-message'],
  resolve: () => ({
    text: '请根据审核反馈继续完善内容，管理员通过后会重新公开显示。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-updated-title',
  order: 629,
  surfaces: ['discussion-composer-updated-title'],
  resolve: () => ({
    text: '讨论已更新',
  }),
})

registerUiCopy({
  key: 'discussion-composer-updated-message',
  order: 630,
  surfaces: ['discussion-composer-updated-message'],
  resolve: () => ({
    text: '新的讨论内容已经保存。',
  }),
})

registerUiCopy({
  key: 'discussion-composer-create-pending-title',
  order: 631,
  surfaces: ['discussion-composer-create-pending-title'],
  resolve: () => ({
    text: '讨论已进入审核队列',
  }),
})

registerUiCopy({
  key: 'discussion-composer-create-pending-message',
  order: 632,
  surfaces: ['discussion-composer-create-pending-message'],
  resolve: () => ({
    text: '管理员通过后，这条讨论才会显示在论坛列表中。',
  }),
})

registerUiCopy({
  key: 'post-composer-content-placeholder',
  order: 620,
  surfaces: ['post-composer-content-placeholder'],
  resolve: () => ({
    text: '输入你的回复... 支持 Markdown、@用户名 和代码块',
  }),
})

registerUiCopy({
  key: 'post-composer-submit',
  order: 630,
  surfaces: ['post-composer-submit'],
  resolve: ({ submitting, uploading, isEditing }) => ({
    text: submitting ? '提交中...' : (uploading ? '上传中...' : (isEditing ? '更新回复' : '发布回复')),
  }),
})

registerUiCopy({
  key: 'post-composer-title',
  order: 631,
  surfaces: ['post-composer-title'],
  resolve: ({ isEditing, postNumber, discussionTitle }) => ({
    text: isEditing
      ? `编辑 #${postNumber || ''}`.trim()
      : (postNumber ? `回复 #${postNumber}` : `回复：${discussionTitle || '讨论'}`),
  }),
})

registerUiCopy({
  key: 'post-composer-subtitle',
  order: 632,
  surfaces: ['post-composer-subtitle'],
  resolve: ({ isEditing, discussionTitle, hasDraftSavedAt, draftSavedAtText, username }) => {
    if (isEditing) {
      return {
        text: `${discussionTitle || '讨论'} · 编辑后会直接更新原帖`,
      }
    }

    if (hasDraftSavedAt) {
      return {
        text: `草稿已保存于 ${draftSavedAtText}`,
      }
    }

    if (username) {
      return {
        text: `${discussionTitle || '讨论'} · @${username}`,
      }
    }

    return {
      text: discussionTitle || '讨论',
    }
  },
})

registerUiCopy({
  key: 'post-composer-minimized-summary',
  order: 633,
  surfaces: ['post-composer-minimized-summary'],
  resolve: ({ isEditing, postNumber, discussionTitle }) => ({
    text: isEditing
      ? `编辑 #${postNumber || ''}`.trim()
      : (postNumber ? `回复 #${postNumber}` : (discussionTitle || '回复讨论')),
  }),
})

registerUiCopy({
  key: 'post-composer-close-title',
  order: 634,
  surfaces: ['post-composer-close-title'],
  resolve: ({ isEditing }) => ({
    text: isEditing ? '关闭编辑器' : '关闭回复框',
  }),
})

registerUiCopy({
  key: 'post-composer-close-message',
  order: 635,
  surfaces: ['post-composer-close-message'],
  resolve: ({ isEditing }) => ({
    text: isEditing
      ? '确定要关闭编辑器吗？未保存修改将丢失。'
      : '确定要关闭回复框吗？当前内容会保留在本地草稿中。',
  }),
})

registerUiCopy({
  key: 'post-composer-close-confirm',
  order: 636,
  surfaces: ['post-composer-close-confirm'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'post-composer-close-cancel',
  order: 637,
  surfaces: ['post-composer-close-cancel'],
  resolve: () => ({
    text: '继续编辑',
  }),
})

registerUiCopy({
  key: 'post-composer-draft-restored',
  order: 638,
  surfaces: ['post-composer-draft-restored'],
  resolve: ({ hasDraftSavedAt, draftSavedAtText }) => ({
    text: hasDraftSavedAt
      ? `已恢复你在 ${draftSavedAtText} 保存的回复草稿。`
      : '已恢复本地回复草稿。',
  }),
})

registerUiCopy({
  key: 'post-composer-draft-restore-error',
  order: 639,
  surfaces: ['post-composer-draft-restore-error'],
  resolve: () => ({
    text: '回复草稿恢复失败。',
  }),
})

registerUiCopy({
  key: 'post-composer-draft-emptied',
  order: 640,
  surfaces: ['post-composer-draft-emptied'],
  resolve: () => ({
    text: '回复草稿已清空。',
  }),
})

registerUiCopy({
  key: 'post-composer-draft-saved',
  order: 641,
  surfaces: ['post-composer-draft-saved'],
  resolve: () => ({
    text: '回复草稿已保存。',
  }),
})

registerUiCopy({
  key: 'post-composer-draft-cleared-local',
  order: 642,
  surfaces: ['post-composer-draft-cleared-local'],
  resolve: () => ({
    text: '已清除本地回复草稿。',
  }),
})

registerUiCopy({
  key: 'post-composer-unsaved-exit-message',
  order: 642,
  surfaces: ['post-composer-unsaved-exit-message'],
  resolve: ({ isEditing }) => ({
    text: isEditing
      ? '你有未保存的帖子编辑内容。确定要离开当前页面吗？'
      : '你有未发布的回复内容。确定要离开当前页面吗？',
  }),
})

registerUiCopy({
  key: 'post-composer-edit-pending-title',
  order: 643,
  surfaces: ['post-composer-edit-pending-title'],
  resolve: () => ({
    text: '回复已重新提交审核',
  }),
})

registerUiCopy({
  key: 'forum-realtime-status-reconnecting',
  order: 645,
  surfaces: ['forum-realtime-status-reconnecting'],
  resolve: () => ({
    text: '论坛实时连接已断开，正在尝试重新连接...',
  }),
})

registerUiCopy({
  key: 'forum-realtime-status-error',
  order: 646,
  surfaces: ['forum-realtime-status-error'],
  resolve: () => ({
    text: '论坛实时连接暂时不可用，稍后会在下次页面交互时重试。',
  }),
})

registerUiCopy({
  key: 'post-composer-edit-pending-message',
  order: 644,
  surfaces: ['post-composer-edit-pending-message'],
  resolve: () => ({
    text: '管理员通过后，这条回复才会重新显示给其他用户。',
  }),
})

registerUiCopy({
  key: 'post-composer-create-pending-title',
  order: 645,
  surfaces: ['post-composer-create-pending-title'],
  resolve: () => ({
    text: '回复已进入审核队列',
  }),
})

registerUiCopy({
  key: 'post-composer-create-pending-message',
  order: 646,
  surfaces: ['post-composer-create-pending-message'],
  resolve: () => ({
    text: '管理员通过后，这条回复才会显示给其他用户。',
  }),
})

registerUiCopy({
  key: 'composer-notice-draft-label',
  order: 646,
  surfaces: ['composer-notice-draft-label'],
  resolve: () => ({
    text: '草稿',
  }),
})

registerUiCopy({
  key: 'composer-notice-upload-label',
  order: 646,
  surfaces: ['composer-notice-upload-label'],
  resolve: () => ({
    text: '上传',
  }),
})

registerUiCopy({
  key: 'composer-notice-preview-label',
  order: 646,
  surfaces: ['composer-notice-preview-label'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'composer-notice-submit-label',
  order: 646,
  surfaces: ['composer-notice-submit-label'],
  resolve: ({ isEditing, isEditingDiscussion, type }) => {
    if (type === 'discussion') {
      return {
        text: isEditingDiscussion ? '保存' : '发布',
      }
    }

    return {
      text: isEditing ? '保存' : '发布',
    }
  },
})

registerUiCopy({
  key: 'composer-upload-progress',
  order: 646,
  surfaces: ['composer-upload-progress'],
  resolve: ({ asImage, fileName }) => ({
    text: `正在上传${asImage ? '图片' : '附件'}：${fileName || ''}`,
  }),
})

registerUiCopy({
  key: 'composer-upload-inserted',
  order: 646,
  surfaces: ['composer-upload-inserted'],
  resolve: ({ asImage }) => ({
    text: `${asImage ? '图片' : '附件'}已插入编辑器`,
  }),
})

registerUiCopy({
  key: 'composer-upload-failed',
  order: 646,
  surfaces: ['composer-upload-failed'],
  resolve: ({ asImage }) => ({
    text: asImage ? '图片上传失败' : '附件上传失败',
  }),
})

registerUiCopy({
  key: 'composer-preview-load-failed',
  order: 646,
  surfaces: ['composer-preview-load-failed'],
  resolve: () => ({
    text: '预览加载失败',
  }),
})

registerUiCopy({
  key: 'composer-submit-blocked',
  order: 646,
  surfaces: ['composer-submit-blocked'],
  resolve: () => ({
    text: '当前内容未通过校验。',
  }),
})

registerUiCopy({
  key: 'composer-submit-failed',
  order: 646,
  surfaces: ['composer-submit-failed'],
  resolve: () => ({
    text: '提交失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'composer-draft-time-fallback',
  order: 646,
  surfaces: ['composer-draft-time-fallback'],
  resolve: () => ({
    text: '刚刚',
  }),
})

registerUiCopy({
  key: 'composer-date-fallback',
  order: 646,
  surfaces: ['composer-date-fallback'],
  resolve: () => ({
    text: '未知时间',
  }),
})

registerUiCopy({
  key: 'verify-email-title',
  order: 640,
  surfaces: ['verify-email-title'],
  resolve: () => ({
    text: '验证邮箱',
  }),
})

registerUiCopy({
  key: 'verify-email-subtitle',
  order: 650,
  surfaces: ['verify-email-subtitle'],
  resolve: () => ({
    text: '确认你的邮箱地址后，账号安全设置会完整开放。',
  }),
})

registerUiCopy({
  key: 'verify-email-loading',
  order: 660,
  surfaces: ['verify-email-loading'],
  resolve: () => ({
    text: '正在验证邮箱，请稍候...',
  }),
})

registerUiCopy({
  key: 'verify-email-idle',
  order: 670,
  surfaces: ['verify-email-idle'],
  resolve: () => ({
    text: '请从邮件中的链接打开本页面，或确认地址中的验证令牌是否完整。',
  }),
})

registerUiCopy({
  key: 'verify-email-login-action',
  order: 680,
  surfaces: ['verify-email-login-action'],
  resolve: () => ({
    text: '前往登录',
  }),
})

registerUiCopy({
  key: 'verify-email-profile-action',
  order: 690,
  surfaces: ['verify-email-profile-action'],
  resolve: () => ({
    text: '返回个人资料',
  }),
})

registerUiCopy({
  key: 'verify-email-success',
  order: 700,
  surfaces: ['verify-email-success'],
  resolve: () => ({
    text: '邮箱验证成功。现在你可以继续登录，或返回个人资料查看最新状态。',
  }),
})

registerUiCopy({
  key: 'verify-email-error',
  order: 710,
  surfaces: ['verify-email-error'],
  resolve: () => ({
    text: '邮箱验证失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'reset-password-title',
  order: 720,
  surfaces: ['reset-password-title'],
  resolve: () => ({
    text: '重置密码',
  }),
})

registerUiCopy({
  key: 'reset-password-subtitle',
  order: 730,
  surfaces: ['reset-password-subtitle'],
  resolve: () => ({
    text: '输入新的密码以完成重置。如果你是通过邮件打开页面，令牌会自动填入。',
  }),
})

registerUiCopy({
  key: 'reset-password-token-label',
  order: 740,
  surfaces: ['reset-password-token-label'],
  resolve: () => ({
    text: '重置令牌',
  }),
})

registerUiCopy({
  key: 'reset-password-new-label',
  order: 750,
  surfaces: ['reset-password-new-label'],
  resolve: () => ({
    text: '新密码',
  }),
})

registerUiCopy({
  key: 'reset-password-confirm-label',
  order: 760,
  surfaces: ['reset-password-confirm-label'],
  resolve: () => ({
    text: '确认新密码',
  }),
})

registerUiCopy({
  key: 'reset-password-back-to-login',
  order: 770,
  surfaces: ['reset-password-back-to-login'],
  resolve: () => ({
    text: '返回登录',
  }),
})

registerUiCopy({
  key: 'reset-password-mismatch-error',
  order: 780,
  surfaces: ['reset-password-mismatch-error'],
  resolve: () => ({
    text: '两次输入的新密码不一致',
  }),
})

registerUiCopy({
  key: 'reset-password-success',
  order: 790,
  surfaces: ['reset-password-success'],
  resolve: () => ({
    text: '密码已重置，正在返回登录页...',
  }),
})

registerUiCopy({
  key: 'reset-password-error',
  order: 800,
  surfaces: ['reset-password-error'],
  resolve: () => ({
    text: '重置失败，请检查令牌或稍后重试',
  }),
})

registerUiCopy({
  key: 'modal-close-label',
  order: 810,
  surfaces: ['modal-close-label', 'post-report-close-label', 'moderation-action-close-label'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'modal-cancel-button',
  order: 820,
  surfaces: ['modal-cancel-button'],
  resolve: () => ({
    text: '取消',
  }),
})

registerUiCopy({
  key: 'modal-submit-error',
  order: 830,
  surfaces: ['modal-submit-error'],
  resolve: () => ({
    text: '提交失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'moderation-action-note-label',
  order: 910,
  surfaces: ['moderation-action-note-label'],
  resolve: () => ({
    text: '处理备注',
  }),
})

registerUiCopy({
  key: 'moderation-action-note-help',
  order: 920,
  surfaces: ['moderation-action-note-help'],
  resolve: () => ({
    text: '备注会同步显示给内容作者，建议简明说明处理原因。',
  }),
})

registerUiCopy({
  key: 'moderation-action-submit-button',
  order: 930,
  surfaces: ['moderation-action-submit-button'],
  resolve: ({ submitting, confirmText }) => ({
    text: submitting ? '提交中...' : (confirmText || '提交'),
  }),
})

registerUiCopy({
  key: 'header-search-open-label',
  order: 1060,
  surfaces: ['header-search-open-label'],
  resolve: () => ({
    text: '打开全局搜索',
  }),
})

registerUiCopy({
  key: 'header-search-clear-label',
  order: 1070,
  surfaces: ['header-search-clear-label'],
  resolve: () => ({
    text: '清除搜索',
  }),
})

registerUiCopy({
  key: 'composer-formatting-toolbar-label',
  order: 1100,
  surfaces: ['composer-formatting-toolbar-label'],
  resolve: () => ({
    text: '格式化工具栏',
  }),
})

registerUiCopy({
  key: 'composer-status-bar-label',
  order: 1110,
  surfaces: ['composer-status-bar-label'],
  resolve: () => ({
    text: '编辑器状态',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-title',
  order: 1120,
  surfaces: ['composer-preview-panel-title'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'discussion-detail-load-previous',
  order: 1130,
  surfaces: ['discussion-detail-load-previous'],
  resolve: () => ({
    text: '加载前面的回复',
  }),
})

registerUiCopy({
  key: 'discussion-detail-load-more',
  order: 1140,
  surfaces: ['discussion-detail-load-more'],
  resolve: () => ({
    text: '加载更多回复',
  }),
})

registerUiCopy({
  key: 'discussion-detail-load-posts-loading',
  order: 1150,
  surfaces: ['discussion-detail-load-posts-loading'],
  resolve: () => ({
    text: '正在加载回复...',
  }),
})

registerUiCopy({
  key: 'discussion-detail-unread-divider',
  order: 1160,
  surfaces: ['discussion-detail-unread-divider'],
  resolve: () => ({
    text: '从这里开始是未读回复',
  }),
})

registerUiCopy({
  key: 'profile-hero-avatar-upload',
  order: 1170,
  surfaces: ['profile-hero-avatar-upload'],
  resolve: ({ uploading }) => ({
    text: uploading ? '上传中...' : '更换头像',
  }),
})

registerUiCopy({
  key: 'profile-avatar-upload-error-title',
  order: 1171,
  surfaces: ['profile-avatar-upload-error-title'],
  resolve: () => ({
    text: '头像上传失败',
  }),
})

registerUiCopy({
  key: 'profile-avatar-upload-error-message',
  order: 1172,
  surfaces: ['profile-avatar-upload-error-message'],
  resolve: () => ({
    text: '未知错误',
  }),
})

registerUiCopy({
  key: 'profile-error-unknown',
  order: 1173,
  surfaces: ['profile-error-unknown'],
  resolve: () => ({
    text: '未知错误',
  }),
})

registerUiCopy({
  key: 'profile-hero-settings-button',
  order: 1180,
  surfaces: ['profile-hero-settings-button'],
  resolve: () => ({
    text: '设置',
  }),
})

registerUiCopy({
  key: 'discussion-list-toolbar-mark-read',
  order: 1190,
  surfaces: ['discussion-list-toolbar-mark-read'],
  resolve: ({ markingAllRead }) => ({
    text: markingAllRead ? '正在标记已读...' : '全部标记为已读',
  }),
})

registerUiCopy({
  key: 'discussion-list-toolbar-refresh',
  order: 1200,
  surfaces: ['discussion-list-toolbar-refresh'],
  resolve: ({ refreshing }) => ({
    text: refreshing ? '正在刷新...' : '刷新',
  }),
})

registerUiCopy({
  key: 'discussion-list-toolbar-sort-label',
  order: 1200,
  surfaces: ['discussion-list-toolbar-sort-label'],
  resolve: ({ code }) => ({
    text: code === 'newest' ? '新主题' : code === 'top' ? '热门' : '最新活跃',
  }),
})

registerUiCopy({
  key: 'discussion-list-refreshing',
  order: 1200,
  surfaces: ['discussion-list-refreshing'],
  resolve: () => ({
    text: '正在刷新讨论',
  }),
})

registerUiCopy({
  key: 'discussion-list-load-more',
  order: 1200,
  surfaces: ['discussion-list-load-more'],
  resolve: () => ({
    text: '加载更多讨论',
  }),
})

registerUiCopy({
  key: 'discussion-list-loading-more',
  order: 1200,
  surfaces: ['discussion-list-loading-more'],
  resolve: () => ({
    text: '正在加载讨论...',
  }),
})

registerUiCopy({
  key: 'composer-header-save-draft',
  order: 1270,
  surfaces: ['composer-header-save-draft'],
  resolve: ({ submitting }) => ({
    text: submitting ? '提交中，暂不可保存草稿' : '保存草稿',
  }),
})

registerUiCopy({
  key: 'composer-header-toggle-minimized',
  order: 1280,
  surfaces: ['composer-header-toggle-minimized'],
  resolve: ({ minimized }) => ({
    text: minimized ? '展开' : '最小化',
  }),
})

registerUiCopy({
  key: 'composer-header-toggle-expanded',
  order: 1290,
  surfaces: ['composer-header-toggle-expanded'],
  resolve: ({ expanded }) => ({
    text: expanded ? '退出全屏' : '全屏',
  }),
})

registerUiCopy({
  key: 'composer-header-close',
  order: 1300,
  surfaces: ['composer-header-close'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'auth-session-close',
  order: 1310,
  surfaces: ['auth-session-close'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'auth-session-title',
  order: 1311,
  surfaces: ['auth-session-title'],
  resolve: ({ mode }) => ({
    text: mode === 'register' ? '加入讨论' : (mode === 'forgot-password' ? '找回密码' : '登录'),
  }),
})

registerUiCopy({
  key: 'auth-session-subtitle',
  order: 1312,
  surfaces: ['auth-session-subtitle'],
  resolve: ({ mode }) => ({
    text: mode === 'register'
      ? '注册完成后即可回到当前页面继续操作。'
      : (mode === 'forgot-password'
          ? '输入注册邮箱，我们会向你发送重置密码链接。'
          : '欢迎回来，登录后即可继续回复、关注和管理你的内容。'),
  }),
})

registerUiCopy({
  key: 'auth-session-eyebrow',
  order: 1313,
  surfaces: ['auth-session-eyebrow'],
  resolve: ({ mode }) => ({
    text: mode === 'register' ? 'Sign Up' : (mode === 'forgot-password' ? 'Recovery' : 'Session'),
  }),
})

registerUiCopy({
  key: 'auth-login-identification-label',
  order: 1314,
  surfaces: ['auth-login-identification-label'],
  resolve: () => ({
    text: '用户名或邮箱',
  }),
})

registerUiCopy({
  key: 'auth-login-password-label',
  order: 1315,
  surfaces: ['auth-login-password-label'],
  resolve: () => ({
    text: '密码',
  }),
})

registerUiCopy({
  key: 'auth-human-verification-label',
  order: 1316,
  surfaces: ['auth-human-verification-label'],
  resolve: () => ({
    text: '真人验证',
  }),
})

registerUiCopy({
  key: 'auth-register-username-label',
  order: 1317,
  surfaces: ['auth-register-username-label'],
  resolve: () => ({
    text: '用户名',
  }),
})

registerUiCopy({
  key: 'auth-register-email-label',
  order: 1318,
  surfaces: ['auth-register-email-label'],
  resolve: () => ({
    text: '邮箱',
  }),
})

registerUiCopy({
  key: 'auth-register-password-label',
  order: 1319,
  surfaces: ['auth-register-password-label'],
  resolve: () => ({
    text: '密码',
  }),
})

registerUiCopy({
  key: 'auth-register-password-confirm-label',
  order: 1319,
  surfaces: ['auth-register-password-confirm-label'],
  resolve: () => ({
    text: '确认密码',
  }),
})

registerUiCopy({
  key: 'auth-forgot-email-label',
  order: 1319,
  surfaces: ['auth-forgot-email-label'],
  resolve: () => ({
    text: '邮箱',
  }),
})

registerUiCopy({
  key: 'auth-turnstile-expired-error',
  order: 1319,
  surfaces: ['auth-turnstile-expired-error'],
  resolve: () => ({
    text: '真人验证已过期，请重新完成验证。',
  }),
})

registerUiCopy({
  key: 'auth-turnstile-load-error',
  order: 1319,
  surfaces: ['auth-turnstile-load-error'],
  resolve: () => ({
    text: '真人验证加载失败，请稍后重试。',
  }),
})

registerUiCopy({
  key: 'auth-login-error',
  order: 1319,
  surfaces: ['auth-login-error'],
  resolve: () => ({
    text: '登录失败，请检查用户名和密码',
  }),
})

registerUiCopy({
  key: 'auth-register-password-mismatch-error',
  order: 1319,
  surfaces: ['auth-register-password-mismatch-error'],
  resolve: () => ({
    text: '两次输入的密码不一致',
  }),
})

registerUiCopy({
  key: 'auth-register-error',
  order: 1319,
  surfaces: ['auth-register-error'],
  resolve: () => ({
    text: '注册失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'auth-register-success',
  order: 1319,
  surfaces: ['auth-register-success'],
  resolve: () => ({
    text: '注册成功，请检查邮箱完成验证。',
  }),
})

registerUiCopy({
  key: 'auth-register-field-error',
  order: 1319,
  surfaces: ['auth-register-field-error'],
  resolve: ({ field, message }) => ({
    text: `${field}: ${message}`,
  }),
})

registerUiCopy({
  key: 'auth-forgot-error',
  order: 1319,
  surfaces: ['auth-forgot-error'],
  resolve: () => ({
    text: '发送失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'auth-session-remember-me',
  order: 1320,
  surfaces: ['auth-session-remember-me'],
  resolve: () => ({
    text: '记住我',
  }),
})

registerUiCopy({
  key: 'discussion-reply-typing-notice',
  order: 1321,
  surfaces: ['discussion-reply-typing-notice'],
  resolve: ({ count, usernames }) => {
    const normalizedNames = Array.isArray(usernames)
      ? usernames.map(value => String(value || '').trim()).filter(Boolean)
      : []

    if (!normalizedNames.length || !count) {
      return { text: '' }
    }
    if (count === 1) {
      return { text: `${normalizedNames[0]} 正在输入...` }
    }
    if (count === 2) {
      return { text: `${normalizedNames[0]}、${normalizedNames[1]} 正在输入...` }
    }
    return { text: `${normalizedNames[0]} 等 ${count} 人正在输入...` }
  },
})

registerUiCopy({
  key: 'auth-session-forgot-link',
  order: 1330,
  surfaces: ['auth-session-forgot-link'],
  resolve: () => ({
    text: '忘记密码？',
  }),
})

registerUiCopy({
  key: 'auth-session-no-account',
  order: 1340,
  surfaces: ['auth-session-no-account'],
  resolve: () => ({
    text: '还没有账号？',
  }),
})

registerUiCopy({
  key: 'auth-session-switch-register',
  order: 1350,
  surfaces: ['auth-session-switch-register'],
  resolve: () => ({
    text: '立即注册',
  }),
})

registerUiCopy({
  key: 'auth-session-has-account',
  order: 1360,
  surfaces: ['auth-session-has-account'],
  resolve: () => ({
    text: '已有账号？',
  }),
})

registerUiCopy({
  key: 'auth-session-switch-login',
  order: 1370,
  surfaces: ['auth-session-switch-login'],
  resolve: () => ({
    text: '立即登录',
  }),
})

registerUiCopy({
  key: 'auth-session-back-login',
  order: 1380,
  surfaces: ['auth-session-back-login'],
  resolve: () => ({
    text: '返回登录',
  }),
})

const ProfileDiscussionSection = defineAsyncComponent(() => import('@/components/profile/ProfileDiscussionSection.vue'))
const ProfilePostSection = defineAsyncComponent(() => import('@/components/profile/ProfilePostSection.vue'))
const ProfileSettingsSection = defineAsyncComponent(() => import('@/components/profile/ProfileSettingsSection.vue'))
const ProfileSecuritySection = defineAsyncComponent(() => import('@/components/profile/ProfileSecuritySection.vue'))

registerProfilePanel({
  key: 'discussions',
  moduleId: 'discussions',
  label: '讨论',
  icon: 'fas fa-bars',
  order: 10,
  badge: ({ user }) => Number(user?.discussion_count || 0),
  resolve: context => ({
    component: ProfileDiscussionSection,
    componentProps: {
      discussions: context.discussions,
      loading: context.loadingDiscussions,
      isOwnProfile: context.isOwnProfile,
      buildDiscussionPath: context.buildDiscussionPath,
      formatDate: context.formatDate,
    },
  }),
})

registerProfilePanel({
  key: 'posts',
  moduleId: 'posts',
  label: '回复',
  icon: 'far fa-comment',
  order: 20,
  badge: ({ user }) => Number(user?.comment_count || 0),
  resolve: context => ({
    component: ProfilePostSection,
    componentProps: {
      posts: context.posts,
      loading: context.loadingPosts,
      isOwnProfile: context.isOwnProfile,
      buildDiscussionPath: context.buildDiscussionPath,
      formatDate: context.formatDate,
    },
  }),
})

registerProfilePanel({
  key: 'settings',
  moduleId: 'users',
  label: '设置',
  icon: 'fas fa-user-cog',
  order: 30,
  isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
  resolve: context => ({
    component: ProfileSettingsSection,
    componentProps: {
      user: context.user,
      editForm: context.editForm,
      preferences: context.preferences,
      saving: context.saving,
      settingsSuccess: context.settingsSuccess,
      settingsError: context.settingsError,
      loadingPreferences: context.loadingPreferences,
      savingPreferences: context.savingPreferences,
      preferencesSuccess: context.preferencesSuccess,
      preferencesError: context.preferencesError,
    },
    componentEvents: {
      saveProfile: context.saveProfile,
      savePreferences: context.savePreferences,
    },
  }),
})

registerProfilePanel({
  key: 'security',
  moduleId: 'users',
  label: '安全',
  icon: 'fas fa-shield-alt',
  order: 40,
  isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
  resolve: context => ({
    component: ProfileSecuritySection,
    componentProps: {
      user: context.user,
      passwordForm: context.passwordForm,
      verificationSending: context.verificationSending,
      verificationSuccess: context.verificationSuccess,
      verificationError: context.verificationError,
      changingPassword: context.changingPassword,
      passwordSuccess: context.passwordSuccess,
      passwordError: context.passwordError,
    },
    componentEvents: {
      resendVerification: context.resendVerificationEmail,
      changePassword: context.changePassword,
    },
  }),
})

function formatComposerSuspensionNotice(user = {}, fallbackMessage) {
  if (!user?.is_suspended) return ''

  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}，${fallbackMessage}`
    : `账号当前已被封禁，${fallbackMessage}`
}

function formatComposerDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

registerComposerNotice({
  key: 'suspension',
  order: 10,
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
  resolve: ({ authStore, type }) => ({
    label: '账号',
    tone: 'warning',
    message: formatComposerSuspensionNotice(
      authStore.user,
      type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
    ),
  }),
})

registerComposerNotice({
  key: 'discussion-tag-permission',
  order: 30,
  isVisible: ({ type, availablePrimaryTagCount }) => {
    return type === 'discussion' && Number(availablePrimaryTagCount || 0) <= 0
  },
  resolve: () => ({
    label: '标签',
    tone: 'warning',
    message: '当前没有可发帖的标签，请联系管理员开放标签权限。',
  }),
})

registerComposerNotice({
  key: 'discussion-tag-selection',
  order: 40,
  isVisible: ({ type, availablePrimaryTagCount, primaryTagId }) => {
    return type === 'discussion' && Number(availablePrimaryTagCount || 0) > 0 && !primaryTagId
  },
  resolve: () => ({
    label: '标签',
    tone: 'info',
    message: '先选择主标签，再发布讨论。',
  }),
})

registerComposerTool({
  key: 'discussion-template',
  order: 15,
  isVisible: ({ type }) => type === 'discussion',
  resolve: () => ({
    title: '插入讨论模板',
    icon: 'fas fa-clipboard-list',
    async run({ content, insertText, selectionStart, selectionEnd }) {
      const template = [
        '## 背景',
        '',
        '简要说明当前问题或主题背景。',
        '',
        '## 现象',
        '',
        '描述你观察到的结果、错误或争议点。',
        '',
        '## 期望',
        '',
        '说明希望获得的帮助、答案或改进方向。'
      ].join('\n')

      const prefix = content.trim() ? '\n\n' : ''
      const replacement = `${prefix}${template}`
      const cursor = selectionStart + replacement.length
      await insertText(replacement, {
        start: selectionStart,
        end: selectionEnd,
        cursor,
      })
    },
  }),
})

registerComposerSubmitGuard({
  key: 'suspension',
  order: 10,
  isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
  check: ({ authStore, type }) => ({
    tone: 'error',
    message: formatComposerSuspensionNotice(
      authStore.user,
      type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
    ),
  }),
})

registerComposerSubmitGuard({
  key: 'discussion-start-permission',
  order: 20,
  isVisible: ({ type, mode }) => type === 'discussion' && mode === 'create',
  check: ({ authStore }) => {
    if (authStore?.canStartDiscussion) return null
    return {
      tone: 'error',
      message: '当前账号没有发起讨论的权限。',
    }
  },
})

registerComposerSubmitGuard({
  key: 'discussion-primary-tag',
  order: 30,
  isVisible: ({ type }) => type === 'discussion',
  check: ({ availablePrimaryTagCount, primaryTagId }) => {
    if (Number(availablePrimaryTagCount || 0) <= 0) {
      return {
        tone: 'error',
        message: '当前没有可用主标签，暂时无法发布讨论。',
      }
    }

    if (primaryTagId) return null
    return {
      tone: 'error',
      message: '请选择主标签后再发布讨论。',
    }
  },
})

registerComposerSecondaryAction({
  key: 'clear-discussion-draft',
  order: 10,
  isVisible: ({ type, isEditing, hasDraftContent }) => type === 'discussion' && !isEditing && Boolean(hasDraftContent),
  resolve: ({ draftSavedAt }) => ({
    label: '清除草稿',
    action: 'clear-draft',
    confirm: draftSavedAt ? {
      title: '清除讨论草稿',
      message: '确定要清除当前讨论草稿吗？',
      confirmText: '清除草稿',
      cancelText: '取消',
      tone: 'danger',
    } : null,
  }),
})

registerComposerSecondaryAction({
  key: 'clear-post-draft',
  order: 10,
  isVisible: ({ type, isEditing, hasDraftContent }) => type === 'post' && !isEditing && Boolean(hasDraftContent),
  resolve: ({ draftSavedAt }) => ({
    label: '清除草稿',
    action: 'clear-draft',
    confirm: draftSavedAt ? {
      title: '清除回复草稿',
      message: '确定要清除当前回复草稿吗？',
      confirmText: '清除草稿',
      cancelText: '取消',
      tone: 'danger',
    } : null,
  }),
})

registerComposerSecondaryAction({
  key: 'cancel-post-edit',
  order: 20,
  isVisible: ({ type, isEditing }) => type === 'post' && Boolean(isEditing),
  resolve: () => ({
    label: '取消编辑',
    action: 'cancel-edit',
    confirm: {
      title: '取消编辑',
      message: '确定放弃当前回复编辑内容吗？未保存修改将丢失。',
      confirmText: '放弃修改',
      cancelText: '继续编辑',
      tone: 'warning',
    },
  }),
})

registerComposerSecondaryAction({
  key: 'save-discussion-draft',
  order: 5,
  isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
    return type === 'discussion' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
  },
  resolve: () => ({
    label: '保存草稿',
    onClick: async ({ composerStore }) => {
      window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
        detail: {
          composerType: 'discussion',
          requestId: composerStore?.current?.requestId || 0,
        },
      }))
    },
  }),
})

registerComposerSecondaryAction({
  key: 'save-post-draft',
  order: 5,
  isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
    return type === 'post' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
  },
  resolve: () => ({
    label: '保存草稿',
    onClick: async ({ composerStore }) => {
      window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
        detail: {
          composerType: 'post',
          requestId: composerStore?.current?.requestId || 0,
        },
      }))
    },
  }),
})

registerComposerStatusItem({
  key: 'discussion-selected-tag',
  order: 10,
  isVisible: ({ type, selectedTagLabel, minimized }) => type === 'discussion' && Boolean(selectedTagLabel) && !minimized,
  resolve: ({ selectedTagLabel }) => ({
    label: '标签',
    value: selectedTagLabel,
  }),
})

registerComposerStatusItem({
  key: 'discussion-editing',
  order: 20,
  isVisible: ({ type, isEditing, minimized }) => type === 'discussion' && Boolean(isEditing) && !minimized,
  resolve: () => ({
    label: '状态',
    value: '编辑讨论',
  }),
})

registerComposerDraftMeta({
  key: 'discussion-draft-saved-at',
  order: 30,
  isVisible: ({ type, draftSavedAt, minimized }) => type === 'discussion' && Boolean(draftSavedAt) && !minimized,
  resolve: ({ draftSavedAt, formatDraftTime }) => ({
    label: '草稿',
    value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
  }),
})

registerComposerStatusItem({
  key: 'post-editing',
  order: 10,
  isVisible: ({ type, isEditing, minimized }) => type === 'post' && Boolean(isEditing) && !minimized,
  resolve: ({ postNumber }) => ({
    label: '状态',
    value: postNumber ? `编辑 #${postNumber}` : '编辑回复',
  }),
})

registerComposerStatusItem({
  key: 'post-target',
  order: 20,
  isVisible: ({ type, discussionTitle, minimized }) => type === 'post' && Boolean(discussionTitle) && !minimized,
  resolve: ({ discussionTitle, username }) => ({
    label: '讨论',
    value: username ? `${discussionTitle} · @${username}` : discussionTitle,
  }),
})

registerComposerDraftMeta({
  key: 'post-draft-saved-at',
  order: 30,
  isVisible: ({ type, draftSavedAt, isEditing, minimized }) => {
    return type === 'post' && !isEditing && Boolean(draftSavedAt) && !minimized
  },
  resolve: ({ draftSavedAt, formatDraftTime }) => ({
    label: '草稿',
    value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
  }),
})
