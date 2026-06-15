import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getDiscussionActions,
  getDiscussionActionHandler,
  getDiscussionListContexts,
  getDiscussionListHero,
  getDiscussionListRequests,
  getAuthChallengeProvider,
  getAuthModalProvider,
  getComposerAutocompleteProviders,
  getComposerDraftMeta,
  getComposerFields,
  getComposerHosts,
  getComposerUploadHandler,
  getFeedbackNote,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getEmptyState,
  getForumNavItems,
  getForumRealtimeEvents,
  getHeaderItems,
  getHeroMetaItems,
  getNotificationRenderers,
  getPageState,
  getProfilePanels,
  getPostActions,
  getPostActionHandler,
  getSearchModalProvider,
  getSearchModalSections,
  getSearchSources,
  getStartDiscussionProvider,
  getStateBlock,
  getUiCopy,
  getPostFlagPanel,
  getPostTypeDefinition,
  getPostReviewBanner,
  getPostStateBadges,
  registerComposerAutocompleteProvider,
  registerComposerDraftMeta,
  registerComposerField,
  registerComposerHost,
  registerComposerUploadHandler,
  registerComposerInitialState,
  registerComposerPayloadContributor,
  registerComposerPreviewTransformer,
  registerComposerSubmitSuccess,
  registerFeedbackNote,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionListContext,
  registerDiscussionListHero,
  registerDiscussionListRequest,
  registerForumNavItem,
  registerForumRealtimeEvent,
  registerForumRuntime,
  registerHeaderItem,
  registerAuthChallengeProvider,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerEmptyState,
  registerHeroMeta,
  registerNotificationRenderer,
  registerPageState,
  registerProfilePanel,
  registerStateBlock,
  registerUiCopy,
  registerPostAction,
  registerPostActionHandler,
  registerPostFlagPanel,
  registerPostReviewBanner,
  registerAuthModalProvider,
  registerPostStateBadge,
  registerPostType,
  registerSearchModalProvider,
  registerSearchModalSection,
  registerSearchSource,
  registerStartDiscussionProvider,
  runComposerInitialStateContributors,
  runComposerPayloadContributors,
  runComposerPreviewTransformers,
  runComposerSubmitSuccess,
  runForumRuntimeHook,
  syncPostTypes,
} from './frontendRegistry.js'
import { getForumRealtimeEventPolicy } from '../../../extensions/realtime/frontend/forum/forumRealtime.js'
import {
  resolveDiscussionAction,
  runDiscussionAction,
  runPostAction,
} from './discussionActionRuntime.js'

function uniqueKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

test('discussion reply state returns the first visible item by order', () => {
  const highOrderKey = uniqueKey('reply-high')
  const lowOrderKey = uniqueKey('reply-low')

  registerDiscussionReplyState({
    key: highOrderKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({ kind: 'notice', message: 'high' }),
  })

  registerDiscussionReplyState({
    key: lowOrderKey,
    order: 10,
    isVisible: () => true,
    resolve: () => ({ kind: 'notice', message: 'low' }),
  })

  const result = getDiscussionReplyState({})

  assert.equal(result.key, lowOrderKey)
  assert.equal(result.message, 'low')
})

test('auth challenge provider resolves generic verification component and payload builder', () => {
  const key = uniqueKey('auth-challenge')
  const component = { name: 'GenericChallenge' }

  registerAuthChallengeProvider({
    key,
    order: 10,
    component,
    componentProps: ({ mode }) => ({ mode, purpose: 'auth' }),
    isVisible: ({ mode }) => mode === 'login',
    buildPayload: ({ token, payload }) => ({
      token,
      payload,
    }),
  })

  const provider = getAuthChallengeProvider({
    mode: 'login',
    token: 'token-a',
    payload: { answer: '42' },
  })

  assert.equal(provider.key, key)
  assert.equal(provider.component, component)
  assert.deepEqual(provider.componentProps, { mode: 'login', purpose: 'auth' })
  assert.deepEqual(provider.buildPayload({ token: 'token-a', payload: { answer: '42' } }), {
    token: 'token-a',
    payload: { answer: '42' },
  })
  assert.equal(getAuthChallengeProvider({ mode: 'register' })?.key === key, false)
})

test('discussion list context and request registrations resolve by surface', () => {
  const contextKey = uniqueKey('discussion-list-context')
  const requestKey = uniqueKey('discussion-list-request')

  registerDiscussionListContext({
    key: contextKey,
    order: 10,
    surfaces: ['discussion-list'],
    isVisible: ({ route }) => route?.name === 'tag-detail',
    resolve: ({ route }) => ({
      currentTagSlug: route.params.slug,
    }),
  })

  registerDiscussionListRequest({
    key: requestKey,
    order: 10,
    surfaces: ['discussion-list-request'],
    resolve: () => ({
      apply({ params }) {
        return {
          ...params,
          tag: 'announcements',
        }
      },
    }),
  })

  const [context] = getDiscussionListContexts({
    surface: 'discussion-list',
    route: { name: 'tag-detail', params: { slug: 'announcements' } },
  })
  const [request] = getDiscussionListRequests({
    surface: 'discussion-list-request',
  })

  assert.equal(context.key, contextKey)
  assert.equal(context.currentTagSlug, 'announcements')
  assert.equal(request.key, requestKey)
  assert.deepEqual(request.apply({ params: { page: 1 } }), {
    page: 1,
    tag: 'announcements',
  })
  assert.deepEqual(getDiscussionListContexts({
    surface: 'other',
    route: { name: 'tag-detail', params: { slug: 'announcements' } },
  }), [])
})

test('discussion list hero resolves first visible hero for surface', () => {
  const heroKey = uniqueKey('discussion-list-hero')

  registerDiscussionListHero({
    key: heroKey,
    order: 10,
    surfaces: ['discussion-list-hero'],
    isVisible: ({ contextSubject }) => Boolean(contextSubject),
    resolve: ({ contextSubject }) => ({
      title: contextSubject.name,
      pill: '标签',
    }),
  })

  const hero = getDiscussionListHero({
    surface: 'discussion-list-hero',
    contextSubject: { name: '公告' },
  })

  assert.equal(hero.key, heroKey)
  assert.equal(hero.title, '公告')
  assert.equal(hero.pill, '标签')
  assert.equal(getDiscussionListHero({ surface: 'other', contextSubject: { name: '公告' } }), null)
})

test('discussion reply state respects surface filtering', () => {
  const scopedKey = uniqueKey('reply-surface')

  registerDiscussionReplyState({
    key: scopedKey,
    order: 10,
    surfaces: ['discussion-reply'],
    isVisible: () => true,
    resolve: () => ({ kind: 'notice', message: 'scoped' }),
  })

  const fallbackResult = getDiscussionReplyState({ surface: 'other-surface' })
  assert.equal(fallbackResult.message, 'low')
  assert.equal(getDiscussionReplyState({}).message, 'low')

  const result = getDiscussionReplyState({ surface: 'discussion-reply' })
  assert.equal(result.key, scopedKey)
  assert.equal(result.message, 'scoped')
})

test('header items resolve dynamic label and icon fields', () => {
  const key = uniqueKey('header-dynamic')

  registerHeaderItem({
    key,
    placement: 'user-menu',
    order: 10,
    icon: ({ state }) => state.icon,
    label: ({ state }) => `主题：${state.label}`,
    isVisible: () => true,
  })

  const [item] = getHeaderItems({ state: { icon: 'fas fa-moon', label: '深色' } }, 'user-menu')

  assert.equal(item.key, key)
  assert.equal(item.icon, 'fas fa-moon')
  assert.equal(item.label, '主题：深色')
})

test('header items preserve custom component registrations', () => {
  const key = uniqueKey('header-component')

  registerHeaderItem({
    key,
    placement: 'after-search',
    order: 10,
    component: 'NotificationMenuComponent',
    componentProps: ({ unread }) => ({ unread }),
    isVisible: () => true,
  })

  const [item] = getHeaderItems({ unread: 5 }, 'after-search')

  assert.equal(item.key, key)
  assert.equal(item.component, 'NotificationMenuComponent')
  assert.deepEqual(item.componentProps, { unread: 5 })
})

test('auth modal provider resolves extension-owned opener by module state', async () => {
  const hiddenKey = uniqueKey('auth-provider-hidden')
  const visibleKey = uniqueKey('auth-provider-visible')
  const calls = []

  registerAuthModalProvider({
    key: hiddenKey,
    moduleId: 'disabled-auth',
    order: 5,
    open() {
      calls.push('hidden')
    },
  })

  registerAuthModalProvider({
    key: visibleKey,
    moduleId: 'users',
    order: 10,
    open(payload) {
      calls.push(payload.mode)
      return 'opened'
    },
  })

  const provider = getAuthModalProvider({
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== 'disabled-auth'
      },
    },
  })

  assert.equal(provider.key, visibleKey)
  assert.equal(await provider.open({ mode: 'login' }), 'opened')
  assert.deepEqual(calls, ['login'])
})

test('search modal provider resolves extension-owned opener by module state', async () => {
  const hiddenKey = uniqueKey('search-provider-hidden')
  const visibleKey = uniqueKey('search-provider-visible')
  const calls = []

  registerSearchModalProvider({
    key: hiddenKey,
    moduleId: 'disabled-search',
    order: 5,
    open() {
      calls.push('hidden')
    },
  })

  registerSearchModalProvider({
    key: visibleKey,
    moduleId: 'search',
    order: 10,
    component: 'SearchModalComponent',
    open(payload) {
      calls.push(payload.initialQuery)
      return 'opened'
    },
  })

  const provider = getSearchModalProvider({
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== 'disabled-search'
      },
    },
  })

  assert.equal(provider.key, visibleKey)
  assert.equal(provider.component, 'SearchModalComponent')
  assert.equal(await provider.open({ initialQuery: 'bias' }), 'opened')
  assert.deepEqual(calls, ['bias'])
})

test('resolved items preserve top-level dynamic fields when resolve omits them', () => {
  const key = uniqueKey('profile-panel-dynamic')

  registerProfilePanel({
    key,
    order: 10,
    label: ({ user }) => `${user.username} 的讨论`,
    icon: ({ user }) => user.is_staff ? 'fas fa-shield-alt' : 'fas fa-user',
    badge: ({ user }) => Number(user.discussion_count || 0),
    isVisible: () => true,
    resolve: () => ({
      component: 'PanelComponent',
    }),
  })

  const [item] = getProfilePanels({
    user: { username: 'admin', is_staff: true, discussion_count: 6 },
  })

  assert.equal(item.key, key)
  assert.equal(item.label, 'admin 的讨论')
  assert.equal(item.icon, 'fas fa-shield-alt')
  assert.equal(item.badge, 6)
})

test('post state badges are ordered and filtered by surface', () => {
  const detailKey = uniqueKey('post-detail')
  const profileKey = uniqueKey('post-profile')

  registerPostStateBadge({
    key: detailKey,
    order: 20,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => Boolean(post?.needsReview),
    resolve: ({ post }) => ({
      label: `${post.count} pending`,
      tone: 'warning',
    }),
  })

  registerPostStateBadge({
    key: profileKey,
    order: 10,
    surfaces: ['profile-post'],
    isVisible: () => true,
    resolve: () => ({
      label: 'profile',
      tone: 'info',
    }),
  })

  const detailBadges = getPostStateBadges({
    post: { needsReview: true, count: 3 },
    surface: 'discussion-post',
  })
  const profileBadges = getPostStateBadges({
    post: { needsReview: true, count: 3 },
    surface: 'profile-post',
  })

  assert.equal(detailBadges.some(item => item.key === detailKey), true)
  assert.equal(detailBadges.some(item => item.key === profileKey), false)
  assert.equal(profileBadges.some(item => item.key === profileKey), true)
  assert.equal(profileBadges.some(item => item.key === detailKey), false)
  assert.equal(detailBadges.find(item => item.key === detailKey).label, '3 pending')
})

test('synced post type metadata preserves registered components', () => {
  const type = uniqueKey('comment-component')
  const component = { name: 'RegisteredPostComponent' }

  registerPostType({
    type,
    label: 'Registered comment',
    component,
    isDefault: true,
  })
  syncPostTypes([{
    code: type,
    label: 'Backend comment',
    is_default: true,
  }])

  const definition = getPostTypeDefinition(type)
  assert.equal(definition.label, 'Backend comment')
  assert.equal(definition.component, component)
})

test('hero meta resolves ordered surface-specific items', () => {
  const discussionMetaKey = uniqueKey('hero-discussion')
  const profileMetaKey = uniqueKey('hero-profile')

  registerHeroMeta({
    key: discussionMetaKey,
    order: 20,
    surfaces: ['discussion-hero'],
    isVisible: ({ discussion }) => Boolean(discussion?.created_at),
    resolve: ({ discussion }) => ({
      icon: 'far fa-clock',
      text: `created ${discussion.created_at}`,
    }),
  })

  registerHeroMeta({
    key: profileMetaKey,
    order: 10,
    surfaces: ['profile-hero'],
    isVisible: ({ isOnline }) => Boolean(isOnline),
    resolve: () => ({
      icon: 'fas fa-circle',
      text: 'online',
    }),
  })

  const discussionItems = getHeroMetaItems({
    surface: 'discussion-hero',
    discussion: { created_at: '2026-05-09T00:00:00Z' },
  })
  const profileItems = getHeroMetaItems({
    surface: 'profile-hero',
    isOnline: true,
  })

  assert.equal(discussionItems.some(item => item.key === discussionMetaKey), true)
  assert.equal(discussionItems.some(item => item.key === profileMetaKey), false)
  assert.equal(profileItems[0].key, profileMetaKey)
  assert.equal(profileItems[0].text, 'online')
})

test('notification renderers normalize module and navigation metadata aliases', () => {
  const rendererKey = uniqueKey('notification-renderer')

  registerNotificationRenderer({
    key: rendererKey,
    type: 'customNotification',
    label: '自定义通知',
    module_id: 'module-alpha',
    navigation_scope: 'post',
  })

  const renderer = getNotificationRenderers().find(item => item.key === rendererKey)

  assert.equal(renderer.moduleId, 'module-alpha')
  assert.equal(renderer.module_id, 'module-alpha')
  assert.equal(renderer.navigationScope, 'post')
  assert.equal(renderer.navigation_scope, 'post')
})

test('registered items with module id are filtered by forum runtime state', () => {
  const disabledModule = 'disabled-module'
  const context = {
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== disabledModule
      },
    },
    authStore: {
      user: {
        id: 1,
        username: 'tester',
        is_staff: false,
      },
    },
    user: {
      id: 1,
      username: 'tester',
      is_staff: false,
      discussion_count: 0,
      comment_count: 0,
    },
  }

  const navKey = uniqueKey('nav-module-filter')
  const profileKey = uniqueKey('profile-module-filter')
  const searchKey = uniqueKey('search-module-filter')
  const discussionActionKey = uniqueKey('discussion-action-module-filter')
  const postActionKey = uniqueKey('post-action-module-filter')

  registerForumNavItem({
    key: navKey,
    moduleId: disabledModule,
    label: '隐藏导航项',
  })
  registerProfilePanel({
    key: profileKey,
    moduleId: disabledModule,
    label: '隐藏资料面板',
    resolve: () => ({ component: 'HiddenPanel' }),
  })
  registerSearchSource({
    key: searchKey,
    type: 'hidden-search',
    routeType: 'hidden-search',
    moduleId: disabledModule,
    label: '隐藏搜索源',
  })
  registerDiscussionAction({
    key: discussionActionKey,
    moduleId: disabledModule,
    label: '隐藏讨论动作',
  })
  registerPostAction({
    key: postActionKey,
    moduleId: disabledModule,
    label: '隐藏帖子动作',
  })

  assert.equal(getForumNavItems(context).some(item => item.key === navKey), false)
  assert.equal(getProfilePanels(context).some(item => item.key === profileKey), false)
  assert.equal(getSearchSources(context).some(item => item.key === searchKey), false)
  assert.equal(getDiscussionActions(context).some(item => item.key === discussionActionKey), false)
  assert.equal(getPostActions(context).some(item => item.key === postActionKey), false)
})

test('forum realtime events resolve extension policy by module state', () => {
  const enabledKey = uniqueKey('realtime-enabled')
  const disabledKey = uniqueKey('realtime-disabled')
  const enabledEventType = `${enabledKey}.event`
  const disabledEventType = `${disabledKey}.event`
  const context = {
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'enabled-module'
      },
    },
  }

  registerForumRealtimeEvent({
    key: enabledKey,
    moduleId: 'enabled-module',
    order: 10,
    eventTypes: [enabledEventType],
    appendPost: true,
    newReply: true,
  })

  registerForumRealtimeEvent({
    key: disabledKey,
    moduleId: 'disabled-module',
    order: 5,
    eventTypes: [disabledEventType],
    refresh: true,
  })

  assert.equal(getForumRealtimeEvents({
    ...context,
    eventType: enabledEventType,
  }).some(item => item.key === enabledKey), true)
  assert.equal(getForumRealtimeEvents({
    ...context,
    eventType: disabledEventType,
  }).some(item => item.key === disabledKey), false)
  assert.deepEqual(getForumRealtimeEventPolicy(enabledEventType, context), {
    appendPost: true,
    newReply: true,
    refresh: false,
    upsertPost: false,
  })
  assert.equal(getForumRealtimeEventPolicy(disabledEventType, context).refresh, false)
})

test('search modal sections resolve by order, surface and module state', () => {
  const earlyKey = uniqueKey('search-modal-section-early')
  const lateKey = uniqueKey('search-modal-section-late')
  const hiddenKey = uniqueKey('search-modal-section-hidden')

  registerSearchModalSection({
    key: lateKey,
    moduleId: 'tags',
    order: 30,
    surfaces: ['search-modal-empty'],
    resolve: () => ({
      title: 'late',
      items: [{ key: 'late-item' }],
    }),
  })

  registerSearchModalSection({
    key: earlyKey,
    moduleId: 'tags',
    order: 10,
    surfaces: ['search-modal-empty'],
    resolve: () => ({
      title: 'early',
      items: [{ key: 'early-item' }],
    }),
  })

  registerSearchModalSection({
    key: hiddenKey,
    moduleId: 'hidden-module',
    order: 5,
    surfaces: ['search-modal-empty'],
    resolve: () => ({
      title: 'hidden',
      items: [{ key: 'hidden-item' }],
    }),
  })

  const context = {
    surface: 'search-modal-empty',
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'tags'
      },
    },
  }
  const sections = getSearchModalSections(context)

  assert.equal(sections.some(item => item.key === hiddenKey), false)
  assert.equal(sections.findIndex(item => item.key === earlyKey) < sections.findIndex(item => item.key === lateKey), true)
  assert.deepEqual(getSearchModalSections({
    ...context,
    surface: 'other-surface',
  }).filter(item => [earlyKey, lateKey].includes(item.key)), [])
})

test('start discussion provider resolves extension-owned handler by module state', () => {
  const enabledKey = uniqueKey('start-discussion-enabled')
  const disabledKey = uniqueKey('start-discussion-disabled')
  const calls = []

  registerStartDiscussionProvider({
    key: disabledKey,
    moduleId: 'disabled-module',
    order: 5,
    start: () => calls.push('disabled'),
  })

  registerStartDiscussionProvider({
    key: enabledKey,
    moduleId: 'discussions',
    order: 10,
    start: ({ source }) => {
      calls.push(source)
      return true
    },
  })

  const provider = getStartDiscussionProvider({
    source: 'test-start',
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'discussions'
      },
    },
  })

  assert.equal(provider.key, enabledKey)
  assert.equal(provider.start({ source: 'test-start' }), true)
  assert.deepEqual(calls, ['test-start'])
})

test('forum runtime hooks run in order and respect module state', async () => {
  const calls = []
  const skippedKey = uniqueKey('runtime-skipped')
  const lateKey = uniqueKey('runtime-late')
  const earlyKey = uniqueKey('runtime-early')

  registerForumRuntime({
    key: skippedKey,
    moduleId: 'disabled-module',
    order: 1,
    onAuthenticated: () => {
      calls.push('skipped')
      return 'skipped'
    },
  })

  registerForumRuntime({
    key: lateKey,
    moduleId: 'enabled-module',
    order: 30,
    onAuthenticated: () => {
      calls.push('late')
      return 'late'
    },
  })

  registerForumRuntime({
    key: earlyKey,
    moduleId: 'enabled-module',
    order: 10,
    onAuthenticated: async () => {
      calls.push('early')
      return 'early'
    },
  })

  const results = await runForumRuntimeHook('onAuthenticated', {
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'enabled-module'
      },
    },
  })

  assert.deepEqual(calls, ['early', 'late'])
  assert.deepEqual(results, ['early', 'late'])
})

test('forum runtime hooks continue after extension failures', async () => {
  const calls = []
  const failingKey = uniqueKey('runtime-failing')
  const stableKey = uniqueKey('runtime-stable')

  registerForumRuntime({
    key: failingKey,
    order: 10,
    onMounted: () => {
      calls.push('failing')
      throw new Error('runtime failed')
    },
  })

  registerForumRuntime({
    key: stableKey,
    order: 20,
    onMounted: () => {
      calls.push('stable')
      return 'stable'
    },
  })

  const previousConsoleError = console.error
  console.error = () => {}
  try {
    const results = await runForumRuntimeHook('onMounted', {})
    assert.deepEqual(calls, ['failing', 'stable'])
    assert.equal(results[0].key, failingKey)
    assert.equal(results[0].error.message, 'runtime failed')
    assert.equal(results[1], 'stable')
  } finally {
    console.error = previousConsoleError
  }
})

test('admin header entry remains visible for staff even when forum modules are filtered', () => {
  const key = uniqueKey('staff-header-item')
  const mobileKey = uniqueKey('staff-mobile-item')

  registerHeaderItem({
    key,
    placement: 'user-menu',
    order: 10,
    label: '管理后台',
    href: '/admin.html',
    isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
  })
  registerHeaderItem({
    key: mobileKey,
    placement: 'mobile-drawer-user',
    order: 10,
    label: '管理后台',
    href: '/admin.html',
    isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
  })

  const staffContext = {
    forumStore: {
      isModuleEnabled() {
        return false
      },
    },
    state: {
      icon: 'fas fa-shield-alt',
      label: '管理员',
    },
    authStore: {
      user: {
        id: 1,
        username: 'admin',
        is_staff: true,
      },
    },
  }

  const userMenuItems = getHeaderItems(staffContext, 'user-menu')
  const mobileUserItems = getHeaderItems(staffContext, 'mobile-drawer-user')

  assert.equal(userMenuItems.some(item => item.key === key), true)
  assert.equal(mobileUserItems.some(item => item.key === mobileKey), true)
})

test('header items preserve function labels and zero badges', () => {
  const key = uniqueKey('header-function-label')

  registerHeaderItem({
    key,
    placement: 'user-menu',
    order: 15,
    label: ({ authStore }) => `积分 ${Number(authStore?.user?.points_balance || 0)}`,
    badge: ({ authStore }) => Number(authStore?.user?.points_balance || 0),
    isVisible: ({ authStore }) => Boolean(authStore?.user),
  })

  const items = getHeaderItems({
    authStore: {
      user: {
        id: 1,
        username: 'tester',
        points_balance: 0,
      },
    },
    state: {
      icon: 'fas fa-coins',
      label: '积分',
    },
  }, 'user-menu')

  const item = items.find(entry => entry.key === key)
  assert.equal(item?.label, '积分 0')
  assert.equal(item?.badge, 0)
})

test('post review banner prefers matching surface-specific item', () => {
  const fallbackKey = uniqueKey('post-review-fallback')
  const scopedKey = uniqueKey('post-review-scoped')

  registerPostReviewBanner({
    key: fallbackKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({
      message: 'fallback',
      tone: 'warning',
      actions: [],
    }),
  })

  registerPostReviewBanner({
    key: scopedKey,
    order: 40,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => post?.review_status === 'pending',
    resolve: () => ({
      message: 'scoped',
      tone: 'warning',
      actions: [{ key: 'approve', label: '审核通过', action: 'approve' }],
    }),
  })

  const surfaceResult = getPostReviewBanner({
    post: { review_status: 'pending' },
    surface: 'discussion-post',
  })
  const fallbackResult = getPostReviewBanner({
    post: { review_status: 'pending' },
    surface: 'other-surface',
  })

  assert.equal(surfaceResult.key, scopedKey)
  assert.equal(surfaceResult.message, 'scoped')
  assert.equal(surfaceResult.actions.length, 1)
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.message, 'fallback')
})

test('discussion review banner prefers matching surface-specific item', () => {
  const fallbackKey = uniqueKey('discussion-review-fallback')
  const scopedKey = uniqueKey('discussion-review-scoped')

  registerDiscussionReviewBanner({
    key: fallbackKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({
      title: 'fallback',
      message: 'fallback message',
      tone: 'warning',
      actions: [],
    }),
  })

  registerDiscussionReviewBanner({
    key: scopedKey,
    order: 40,
    surfaces: ['discussion-hero'],
    isVisible: ({ discussion }) => discussion?.review_status === 'pending',
    resolve: () => ({
      title: 'scoped',
      message: 'scoped message',
      tone: 'warning',
      actions: [{ key: 'approve', label: '审核通过', action: 'approve' }],
    }),
  })

  const surfaceResult = getDiscussionReviewBanner({
    discussion: { review_status: 'pending' },
    surface: 'discussion-hero',
  })
  const fallbackResult = getDiscussionReviewBanner({
    discussion: { review_status: 'pending' },
    surface: 'other-surface',
  })

  assert.equal(surfaceResult.key, scopedKey)
  assert.equal(surfaceResult.title, 'scoped')
  assert.equal(surfaceResult.actions.length, 1)
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.message, 'fallback message')
})

test('post flag panel prefers matching surface-specific item', () => {
  const fallbackKey = uniqueKey('post-flag-fallback')
  const scopedKey = uniqueKey('post-flag-scoped')

  registerPostFlagPanel({
    key: fallbackKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({
      title: 'fallback',
      description: 'fallback description',
      items: [],
      actions: [],
    }),
  })

  registerPostFlagPanel({
    key: scopedKey,
    order: 40,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => Boolean(post?.open_flag_count > 0),
    resolve: ({ post }) => ({
      title: 'scoped',
      description: 'scoped description',
      items: [{ key: 1, reason: 'spam', userLabel: 'mod', message: 'details' }],
      actions: [{ key: 'resolved', label: `${post.open_flag_count} actions`, status: 'resolved' }],
    }),
  })

  const surfaceResult = getPostFlagPanel({
    post: { open_flag_count: 2 },
    surface: 'discussion-post',
  })
  const fallbackResult = getPostFlagPanel({
    post: { open_flag_count: 2 },
    surface: 'other-surface',
  })

  assert.equal(surfaceResult.key, scopedKey)
  assert.equal(surfaceResult.title, 'scoped')
  assert.equal(surfaceResult.items.length, 1)
  assert.equal(surfaceResult.actions[0].label, '2 actions')
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.description, 'fallback description')
})

test('feedback note registry prefers matching surface-specific item', () => {
  const fallbackKey = uniqueKey('review-note-fallback')
  const scopedKey = uniqueKey('review-note-scoped')

  registerFeedbackNote({
    key: fallbackKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({
      text: 'fallback note',
    }),
  })

  registerFeedbackNote({
    key: scopedKey,
    order: 40,
    surfaces: ['profile-post'],
    isVisible: ({ post }) => Boolean(post?.review_note),
    resolve: ({ post }) => ({
      text: `scoped note: ${post.review_note}`,
    }),
  })

  const surfaceResult = getFeedbackNote({
    post: { review_note: 'detail' },
    surface: 'profile-post',
  })
  const fallbackResult = getFeedbackNote({
    post: { review_note: 'detail' },
    surface: 'other-surface',
  })

  assert.equal(surfaceResult.key, scopedKey)
  assert.equal(surfaceResult.text, 'scoped note: detail')
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.text, 'fallback note')
})

test('empty state prefers matching surface-specific item', () => {
  const fallbackKey = uniqueKey('empty-fallback')
  const scopedKey = uniqueKey('empty-scoped')

  registerEmptyState({
    key: fallbackKey,
    order: 30,
    isVisible: () => true,
    resolve: () => ({
      text: 'fallback empty',
    }),
  })

  registerEmptyState({
    key: scopedKey,
    order: 40,
    surfaces: ['profile-post-empty'],
    isVisible: ({ posts }) => Array.isArray(posts) && posts.length === 0,
    resolve: ({ isOwnProfile }) => ({
      text: isOwnProfile ? 'my empty' : 'other empty',
    }),
  })

  const surfaceResult = getEmptyState({
    posts: [],
    isOwnProfile: true,
    surface: 'profile-post-empty',
  })
  const fallbackResult = getEmptyState({
    posts: [],
    isOwnProfile: true,
    surface: 'other-surface',
  })

  assert.equal(surfaceResult.key, scopedKey)
  assert.equal(surfaceResult.text, 'my empty')
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.text, 'fallback empty')
})

test('empty state resolves discussion list entries by list context', () => {
  const followingKey = uniqueKey('discussion-list-following-empty')
  const defaultKey = uniqueKey('discussion-list-default-empty')

  registerEmptyState({
    key: followingKey,
    order: 10,
    surfaces: ['discussion-list-empty'],
    isVisible: ({ isFollowingPage }) => Boolean(isFollowingPage),
    resolve: () => ({
      text: 'following empty',
    }),
  })

  registerEmptyState({
    key: defaultKey,
    order: 20,
    surfaces: ['discussion-list-empty'],
    isVisible: () => true,
    resolve: () => ({
      text: 'discussion default empty',
    }),
  })

  const followingResult = getEmptyState({
    surface: 'discussion-list-empty',
    isFollowingPage: true,
    listFilter: 'all',
    currentTag: null,
  })
  const defaultResult = getEmptyState({
    surface: 'discussion-list-empty',
    isFollowingPage: false,
    listFilter: 'all',
    currentTag: null,
  })

  assert.equal(followingResult.key, followingKey)
  assert.equal(followingResult.text, 'following empty')
  assert.equal(defaultResult.key, defaultKey)
  assert.equal(defaultResult.text, 'discussion default empty')
})

test('empty state resolves filtered list entries by filter context', () => {
  const filteredKey = uniqueKey('filtered-list-empty')
  const defaultKey = uniqueKey('filtered-list-default-empty')

  registerEmptyState({
    key: filteredKey,
    order: 10,
    surfaces: ['filtered-list-empty'],
    isVisible: ({ items, filteredOnly }) => Array.isArray(items) && items.length === 0 && Boolean(filteredOnly),
    resolve: () => ({
      text: 'filtered empty',
    }),
  })

  registerEmptyState({
    key: defaultKey,
    order: 20,
    surfaces: ['filtered-list-empty'],
    isVisible: ({ items }) => Array.isArray(items) && items.length === 0,
    resolve: () => ({
      text: 'filtered default empty',
    }),
  })

  const filteredResult = getEmptyState({
    surface: 'filtered-list-empty',
    items: [],
    filteredOnly: true,
    activeType: '',
  })
  const defaultResult = getEmptyState({
    surface: 'filtered-list-empty',
    items: [],
    filteredOnly: false,
    activeType: '',
  })

  assert.equal(filteredResult.key, filteredKey)
  assert.equal(filteredResult.text, 'filtered empty')
  assert.equal(defaultResult.key, defaultKey)
  assert.equal(defaultResult.text, 'filtered default empty')
})

test('empty state resolves resource surface entries', () => {
  const collectionKey = uniqueKey('resource-collection-empty')
  const relatedItemKey = uniqueKey('resource-related-empty')

  registerEmptyState({
    key: collectionKey,
    order: 10,
    surfaces: ['resource-collection-empty'],
    isVisible: ({ resources }) => Array.isArray(resources) && resources.length === 0,
    resolve: () => ({
      text: 'resources empty',
    }),
  })

  registerEmptyState({
    key: relatedItemKey,
    order: 20,
    surfaces: ['resource-related-empty'],
    isVisible: ({ resource }) => !resource?.last_item,
    resolve: ({ resource }) => ({
      text: `${resource?.name || 'resource'} no related item`,
    }),
  })

  const collectionResult = getEmptyState({
    surface: 'resource-collection-empty',
    resources: [],
  })
  const relatedItemResult = getEmptyState({
    surface: 'resource-related-empty',
    resource: { name: 'Alpha', last_item: null },
  })

  assert.equal(collectionResult.key, collectionKey)
  assert.equal(collectionResult.text, 'resources empty')
  assert.equal(relatedItemResult.key, relatedItemKey)
  assert.equal(relatedItemResult.text, 'Alpha no related item')
})

test('empty state resolves search page and modal entries by query state', () => {
  const searchPageIdleKey = uniqueKey('search-page-idle')
  const searchModalEmptyKey = uniqueKey('search-modal-empty')

  registerEmptyState({
    key: searchPageIdleKey,
    order: 10,
    surfaces: ['search-page-idle'],
    isVisible: ({ hasQuery }) => !hasQuery,
    resolve: () => ({
      text: 'search idle',
    }),
  })

  registerEmptyState({
    key: searchModalEmptyKey,
    order: 20,
    surfaces: ['search-modal-empty'],
    isVisible: ({ hasQuery }) => Boolean(hasQuery),
    resolve: ({ searchType }) => ({
      text: `search empty: ${searchType}`,
    }),
  })

  const idleResult = getEmptyState({
    surface: 'search-page-idle',
    hasQuery: false,
    searchType: 'all',
  })
  const emptyResult = getEmptyState({
    surface: 'search-modal-empty',
    hasQuery: true,
    searchType: 'posts',
  })

  assert.equal(idleResult.key, searchPageIdleKey)
  assert.equal(idleResult.text, 'search idle')
  assert.equal(emptyResult.key, searchModalEmptyKey)
  assert.equal(emptyResult.text, 'search empty: posts')
})

test('page state resolves surface entries by loading and resource presence', () => {
  const loadingKey = uniqueKey('page-loading')
  const missingKey = uniqueKey('page-missing')

  registerPageState({
    key: loadingKey,
    order: 10,
    surfaces: ['discussion-detail-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: 'detail loading',
    }),
  })

  registerPageState({
    key: missingKey,
    order: 20,
    surfaces: ['profile-not-found'],
    isVisible: ({ loading, user }) => !loading && !user,
    resolve: () => ({
      text: 'profile missing',
    }),
  })

  const loadingResult = getPageState({
    surface: 'discussion-detail-loading',
    loading: true,
    discussion: null,
  })
  const missingResult = getPageState({
    surface: 'profile-not-found',
    loading: false,
    user: null,
  })

  assert.equal(loadingResult.key, loadingKey)
  assert.equal(loadingResult.text, 'detail loading')
  assert.equal(missingResult.key, missingKey)
  assert.equal(missingResult.text, 'profile missing')
})

test('state block resolves surface entries by loading and item state', () => {
  const loadingKey = uniqueKey('state-loading')
  const emptyKey = uniqueKey('state-empty')

  registerStateBlock({
    key: loadingKey,
    order: 10,
    surfaces: ['search-page-loading'],
    isVisible: ({ loading, hasQuery }) => Boolean(loading) && Boolean(hasQuery),
    resolve: () => ({
      text: 'search loading',
    }),
  })

  registerStateBlock({
    key: emptyKey,
    order: 20,
    surfaces: ['composer-mention-empty'],
    isVisible: ({ loading, itemCount }) => !loading && Number(itemCount || 0) === 0,
    resolve: () => ({
      text: 'mention empty',
    }),
  })

  const loadingResult = getStateBlock({
    surface: 'search-page-loading',
    loading: true,
    hasQuery: true,
  })
  const emptyResult = getStateBlock({
    surface: 'composer-mention-empty',
    loading: false,
    itemCount: 0,
  })

  assert.equal(loadingResult.key, loadingKey)
  assert.equal(loadingResult.text, 'search loading')
  assert.equal(emptyResult.key, emptyKey)
  assert.equal(emptyResult.text, 'mention empty')
})

test('ui copy resolves surface entries by context', () => {
  const previewKey = uniqueKey('ui-preview')
  const turnstileKey = uniqueKey('ui-turnstile')

  registerUiCopy({
    key: previewKey,
    order: 10,
    surfaces: ['post-composer-preview-status'],
    isVisible: ({ previewLoading }) => Boolean(previewLoading),
    resolve: () => ({
      text: 'preview syncing',
    }),
  })

  registerUiCopy({
    key: turnstileKey,
    order: 20,
    surfaces: ['auth-turnstile-status'],
    isVisible: ({ humanVerificationRequired, hasToken }) => Boolean(humanVerificationRequired) && !hasToken,
    resolve: () => ({
      text: 'complete verification',
    }),
  })

  const previewResult = getUiCopy({
    surface: 'post-composer-preview-status',
    previewLoading: true,
  })
  const turnstileResult = getUiCopy({
    surface: 'auth-turnstile-status',
    humanVerificationRequired: true,
    hasToken: false,
  })

  assert.equal(previewResult.key, previewKey)
  assert.equal(previewResult.text, 'preview syncing')
  assert.equal(turnstileResult.key, turnstileKey)
  assert.equal(turnstileResult.text, 'complete verification')
})

test('ui copy resolves button and placeholder variants by loading state', () => {
  const submitKey = uniqueKey('ui-submit')
  const placeholderKey = uniqueKey('ui-placeholder')

  registerUiCopy({
    key: submitKey,
    order: 10,
    surfaces: ['reset-password-submit'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: 'reset submitting',
    }),
  })

  registerUiCopy({
    key: placeholderKey,
    order: 20,
    surfaces: ['header-search-placeholder'],
    resolve: () => ({
      text: 'search site',
    }),
  })

  const submitResult = getUiCopy({
    surface: 'reset-password-submit',
    loading: true,
  })
  const placeholderResult = getUiCopy({
    surface: 'header-search-placeholder',
  })

  assert.equal(submitResult.key, submitKey)
  assert.equal(submitResult.text, 'reset submitting')
  assert.equal(placeholderResult.key, placeholderKey)
  assert.equal(placeholderResult.text, 'search site')
})

test('ui copy resolves contextual search and submit copy', () => {
  const searchLabelKey = uniqueKey('ui-mobile-search')
  const submitKey = uniqueKey('ui-composer-submit')

  registerUiCopy({
    key: searchLabelKey,
    order: 10,
    surfaces: ['mobile-drawer-search-label'],
    resolve: ({ currentSearchQuery }) => ({
      text: currentSearchQuery ? `lookup: ${currentSearchQuery}` : 'lookup forum',
    }),
  })

  registerUiCopy({
    key: submitKey,
    order: 20,
    surfaces: ['discussion-composer-submit'],
    resolve: ({ submitting, uploading, isEditingDiscussion }) => ({
      text: submitting
        ? 'saving'
        : (uploading ? 'uploading attachment' : (isEditingDiscussion ? 'update discussion' : 'publish discussion')),
    }),
  })

  const searchLabelResult = getUiCopy({
    surface: 'mobile-drawer-search-label',
    currentSearchQuery: 'Vue',
  })
  const submitResult = getUiCopy({
    surface: 'discussion-composer-submit',
    submitting: false,
    uploading: true,
    isEditingDiscussion: true,
  })

  assert.equal(searchLabelResult.key, searchLabelKey)
  assert.equal(searchLabelResult.text, 'lookup: Vue')
  assert.equal(submitResult.key, submitKey)
  assert.equal(submitResult.text, 'uploading attachment')
})

test('ui copy resolves modal and notification contextual copy', () => {
  const reportDescriptionKey = uniqueKey('ui-report-description')
  const notificationMarkKey = uniqueKey('ui-notification-mark')

  registerUiCopy({
    key: reportDescriptionKey,
    order: 10,
    surfaces: ['post-report-description'],
    resolve: ({ postNumber }) => ({
      text: `report post #${postNumber}`,
    }),
  })

  registerUiCopy({
    key: notificationMarkKey,
    order: 20,
    surfaces: ['notification-page-mark-all'],
    resolve: ({ marking, hasActiveFilter }) => ({
      text: marking ? 'working' : (hasActiveFilter ? 'mark filtered' : 'mark all'),
    }),
  })

  const reportDescriptionResult = getUiCopy({
    surface: 'post-report-description',
    postNumber: 12,
  })
  const notificationMarkResult = getUiCopy({
    surface: 'notification-page-mark-all',
    marking: false,
    hasActiveFilter: true,
  })

  assert.equal(reportDescriptionResult.key, reportDescriptionKey)
  assert.equal(reportDescriptionResult.text, 'report post #12')
  assert.equal(notificationMarkResult.key, notificationMarkKey)
  assert.equal(notificationMarkResult.text, 'mark filtered')
})

test('ui copy resolves toolbar and composer header contextual copy', () => {
  const refreshKey = uniqueKey('ui-toolbar-refresh')
  const minimizeKey = uniqueKey('ui-composer-minimize')

  registerUiCopy({
    key: refreshKey,
    order: 10,
    surfaces: ['discussion-list-toolbar-refresh'],
    resolve: ({ refreshing }) => ({
      text: refreshing ? 'refreshing list' : 'refresh list',
    }),
  })

  registerUiCopy({
    key: minimizeKey,
    order: 20,
    surfaces: ['composer-header-toggle-minimized'],
    resolve: ({ minimized }) => ({
      text: minimized ? 'expand composer' : 'minimize composer',
    }),
  })

  const refreshResult = getUiCopy({
    surface: 'discussion-list-toolbar-refresh',
    refreshing: true,
  })
  const minimizeResult = getUiCopy({
    surface: 'composer-header-toggle-minimized',
    minimized: false,
  })

  assert.equal(refreshResult.key, refreshKey)
  assert.equal(refreshResult.text, 'refreshing list')
  assert.equal(minimizeResult.key, minimizeKey)
  assert.equal(minimizeResult.text, 'minimize composer')
})

test('ui copy resolves search modal and page contextual copy', () => {
  const sectionKey = uniqueKey('ui-search-section')
  const heroKey = uniqueKey('ui-search-hero')

  registerUiCopy({
    key: sectionKey,
    order: 10,
    surfaces: ['search-modal-section-link'],
    resolve: () => ({
      text: 'only {label}',
    }),
  })

  registerUiCopy({
    key: heroKey,
    order: 20,
    surfaces: ['search-page-hero-title'],
    resolve: ({ query }) => ({
      text: query ? `query:${query}` : 'query:none',
    }),
  })

  const sectionResult = getUiCopy({
    surface: 'search-modal-section-link',
  })
  const heroResult = getUiCopy({
    surface: 'search-page-hero-title',
    query: 'Vue',
  })

  assert.equal(sectionResult.key, sectionKey)
  assert.equal(sectionResult.text, 'only {label}')
  assert.equal(heroResult.key, heroKey)
  assert.equal(heroResult.text, 'query:Vue')
})

test('ui copy resolves home and contextual start discussion copy', () => {
  const homeKey = uniqueKey('ui-home-hero')
  const startKey = uniqueKey('ui-start-discussion')

  registerUiCopy({
    key: homeKey,
    order: 10,
    surfaces: ['home-hero-description'],
    resolve: () => ({
      text: 'forum home',
    }),
  })

  registerUiCopy({
    key: startKey,
    order: 20,
    surfaces: ['start-discussion-button'],
    resolve: ({ hasContextSubject, subjectName }) => ({
      text: hasContextSubject ? `start in ${subjectName}` : 'start discussion',
    }),
  })

  const homeResult = getUiCopy({
    surface: 'home-hero-description',
  })
  const startResult = getUiCopy({
    surface: 'start-discussion-button',
    hasContextSubject: true,
    subjectName: 'Vue',
  })

  assert.equal(homeResult.key, homeKey)
  assert.equal(homeResult.text, 'forum home')
  assert.equal(startResult.key, startKey)
  assert.equal(startResult.text, 'start in Vue')
})

test('ui copy resolves filter and stat labels', () => {
  const filterKey = uniqueKey('ui-filter-label')
  const statKey = uniqueKey('ui-stat-label')

  registerUiCopy({
    key: filterKey,
    order: 10,
    surfaces: ['search-filter-item-label'],
    resolve: ({ label, count }) => ({
      text: `${label}:${count}`,
    }),
  })

  registerUiCopy({
    key: statKey,
    order: 20,
    surfaces: ['search-stat-label'],
    resolve: ({ key, count }) => ({
      text: `${key}:${count}`,
    }),
  })

  const filterResult = getUiCopy({
    surface: 'search-filter-item-label',
    label: '讨论',
    count: 12,
  })
  const statResult = getUiCopy({
    surface: 'search-stat-label',
    key: 'users',
    count: 3,
  })

  assert.equal(filterResult.key, filterKey)
  assert.equal(filterResult.text, '讨论:12')
  assert.equal(statResult.key, statKey)
  assert.equal(statResult.text, 'users:3')
})

test('ui copy resolves notification confirm and alert copy', () => {
  const confirmKey = uniqueKey('ui-notification-confirm')
  const alertKey = uniqueKey('ui-notification-alert')

  registerUiCopy({
    key: confirmKey,
    order: 10,
    surfaces: ['notification-confirm-mark-all-message'],
    resolve: ({ unreadCount }) => ({
      text: `confirm:${unreadCount}`,
    }),
  })

  registerUiCopy({
    key: alertKey,
    order: 20,
    surfaces: ['notification-alert-mark-all-success-message'],
    resolve: ({ hasActiveFilter }) => ({
      text: hasActiveFilter ? 'alert:filtered' : 'alert:page',
    }),
  })

  const confirmResult = getUiCopy({
    surface: 'notification-confirm-mark-all-message',
    unreadCount: 5,
  })
  const alertResult = getUiCopy({
    surface: 'notification-alert-mark-all-success-message',
    hasActiveFilter: true,
  })

  assert.equal(confirmResult.key, confirmKey)
  assert.equal(confirmResult.text, 'confirm:5')
  assert.equal(alertResult.key, alertKey)
  assert.equal(alertResult.text, 'alert:filtered')
})

test('ui copy resolves discussion and post action copy', () => {
  const discussionKey = uniqueKey('ui-discussion-action')
  const postKey = uniqueKey('ui-post-action')

  registerUiCopy({
    key: discussionKey,
    order: 10,
    surfaces: ['discussion-action-toggle-hide-confirm-message'],
    resolve: ({ isHidden }) => ({
      text: isHidden ? 'show discussion' : 'hide discussion',
    }),
  })

  registerUiCopy({
    key: postKey,
    order: 20,
    surfaces: ['post-action-toggle-hide-confirm-message'],
    resolve: ({ postNumber }) => ({
      text: `toggle post ${postNumber}`,
    }),
  })

  const discussionResult = getUiCopy({
    surface: 'discussion-action-toggle-hide-confirm-message',
    isHidden: false,
  })
  const postResult = getUiCopy({
    surface: 'post-action-toggle-hide-confirm-message',
    postNumber: 9,
  })

  assert.equal(discussionResult.key, discussionKey)
  assert.equal(discussionResult.text, 'hide discussion')
  assert.equal(postResult.key, postKey)
  assert.equal(postResult.text, 'toggle post 9')
})

test('ui copy resolves sidebar and action menu helper copy', () => {
  const sidebarKey = uniqueKey('ui-sidebar-copy')
  const titleKey = uniqueKey('ui-action-title')

  registerUiCopy({
    key: sidebarKey,
    order: 10,
    surfaces: ['discussion-sidebar-subscribed'],
    resolve: () => ({
      text: 'sidebar subscribed',
    }),
  })

  registerUiCopy({
    key: titleKey,
    order: 20,
    surfaces: ['forum-action-menu-item-title'],
    resolve: ({ disabledReason }) => ({
      text: `title:${disabledReason}`,
    }),
  })

  const sidebarResult = getUiCopy({
    surface: 'discussion-sidebar-subscribed',
  })
  const titleResult = getUiCopy({
    surface: 'forum-action-menu-item-title',
    disabledReason: 'busy',
  })

  assert.equal(sidebarResult.key, sidebarKey)
  assert.equal(sidebarResult.text, 'sidebar subscribed')
  assert.equal(titleResult.key, titleKey)
  assert.equal(titleResult.text, 'title:busy')
})

test('ui copy resolves discussion sidebar scrubber and list sidebar copy', () => {
  const scrubberStartKey = uniqueKey('ui-scrubber-start')
  const scrubberEndKey = uniqueKey('ui-scrubber-end')
  const profileLinkKey = uniqueKey('ui-profile-link')

  registerUiCopy({
    key: scrubberStartKey,
    order: 10,
    surfaces: ['discussion-sidebar-scrubber-start'],
    resolve: () => ({
      text: 'first post',
    }),
  })

  registerUiCopy({
    key: scrubberEndKey,
    order: 20,
    surfaces: ['discussion-sidebar-scrubber-end'],
    resolve: () => ({
      text: 'now',
    }),
  })

  registerUiCopy({
    key: profileLinkKey,
    order: 30,
    surfaces: ['discussion-list-sidebar-profile-link'],
    resolve: () => ({
      text: 'my profile',
    }),
  })

  const scrubberStartResult = getUiCopy({
    surface: 'discussion-sidebar-scrubber-start',
  })
  const scrubberEndResult = getUiCopy({
    surface: 'discussion-sidebar-scrubber-end',
  })
  const profileLinkResult = getUiCopy({
    surface: 'discussion-list-sidebar-profile-link',
  })

  assert.equal(scrubberStartResult.key, scrubberStartKey)
  assert.equal(scrubberStartResult.text, 'first post')
  assert.equal(scrubberEndResult.key, scrubberEndKey)
  assert.equal(scrubberEndResult.text, 'now')
  assert.equal(profileLinkResult.key, profileLinkKey)
  assert.equal(profileLinkResult.text, 'my profile')
})

test('ui copy resolves mobile header and discussion list navigation copy', () => {
  const pageTitleKey = uniqueKey('ui-mobile-page-title')
  const leftActionKey = uniqueKey('ui-mobile-left-action')
  const rightActionKey = uniqueKey('ui-mobile-right-action')
  const filterLabelKey = uniqueKey('ui-discussion-filter-label')
  const actionTitleKey = uniqueKey('ui-discussion-action-title')
  const retryMessageKey = uniqueKey('ui-discussion-action-retry')
  const filterHeroKey = uniqueKey('ui-discussion-filter-hero')
  const pageMetaKey = uniqueKey('ui-discussion-page-meta')

  registerUiCopy({
    key: pageTitleKey,
    order: 10,
    surfaces: ['header-mobile-page-title'],
    resolve: ({ routeName }) => ({
      text: `page:${routeName}`,
    }),
  })

  registerUiCopy({
    key: leftActionKey,
    order: 20,
    surfaces: ['header-mobile-left-action-label'],
    resolve: ({ leftAction }) => ({
      text: `left:${leftAction}`,
    }),
  })

  registerUiCopy({
    key: rightActionKey,
    order: 30,
    surfaces: ['header-mobile-right-action-label'],
    resolve: ({ actionType }) => ({
      text: `right:${actionType}`,
    }),
  })

  registerUiCopy({
    key: filterLabelKey,
    order: 40,
    surfaces: ['discussion-list-default-filter-label'],
    resolve: ({ code }) => ({
      text: `filter:${code}`,
    }),
  })

  registerUiCopy({
    key: actionTitleKey,
    order: 50,
    surfaces: ['discussion-list-action-failed-title'],
    resolve: ({ actionType }) => ({
      text: `action:${actionType}`,
    }),
  })

  registerUiCopy({
    key: retryMessageKey,
    order: 60,
    surfaces: ['discussion-list-action-retry-message'],
    resolve: () => ({
      text: 'retry:later',
    }),
  })

  registerUiCopy({
    key: filterHeroKey,
    order: 70,
    surfaces: ['discussion-list-filter-hero-title'],
    resolve: ({ listFilter }) => ({
      text: `hero:${listFilter}`,
    }),
  })

  registerUiCopy({
    key: pageMetaKey,
    order: 80,
    surfaces: ['discussion-list-page-meta-title'],
    resolve: ({ listFilter, subjectName, hasSearchQuery }) => ({
      text: `meta:${listFilter}:${subjectName}:${hasSearchQuery}`,
    }),
  })

  const pageTitleResult = getUiCopy({
    surface: 'header-mobile-page-title',
    routeName: 'search',
    listFilter: 'unread',
  })
  const leftActionResult = getUiCopy({
    surface: 'header-mobile-left-action-label',
    leftAction: 'back',
  })
  const rightActionResult = getUiCopy({
    surface: 'header-mobile-right-action-label',
    actionType: 'discussion-menu',
  })
  const filterLabelResult = getUiCopy({
    surface: 'discussion-list-default-filter-label',
    code: 'following',
  })
  const actionTitleResult = getUiCopy({
    surface: 'discussion-list-action-failed-title',
    actionType: 'load-more',
  })
  const retryMessageResult = getUiCopy({
    surface: 'discussion-list-action-retry-message',
  })
  const filterHeroResult = getUiCopy({
    surface: 'discussion-list-filter-hero-title',
    listFilter: 'unread',
  })
  const pageMetaResult = getUiCopy({
    surface: 'discussion-list-page-meta-title',
    listFilter: 'my',
    subjectName: '前端',
    hasSearchQuery: true,
  })

  assert.equal(pageTitleResult.key, pageTitleKey)
  assert.equal(pageTitleResult.text, 'page:search')
  assert.equal(leftActionResult.key, leftActionKey)
  assert.equal(leftActionResult.text, 'left:back')
  assert.equal(rightActionResult.key, rightActionKey)
  assert.equal(rightActionResult.text, 'right:discussion-menu')
  assert.equal(filterLabelResult.key, filterLabelKey)
  assert.equal(filterLabelResult.text, 'filter:following')
  assert.equal(actionTitleResult.key, actionTitleKey)
  assert.equal(actionTitleResult.text, 'action:load-more')
  assert.equal(retryMessageResult.key, retryMessageKey)
  assert.equal(retryMessageResult.text, 'retry:later')
  assert.equal(filterHeroResult.key, filterHeroKey)
  assert.equal(filterHeroResult.text, 'hero:unread')
  assert.equal(pageMetaResult.key, pageMetaKey)
  assert.equal(pageMetaResult.text, 'meta:my:前端:true')
})

test('ui copy resolves discussion event post copy', () => {
  const jumpKey = uniqueKey('ui-event-jump')
  const approvedKey = uniqueKey('ui-event-approved')
  const postHiddenKey = uniqueKey('ui-event-post-hidden')
  const fallbackKey = uniqueKey('ui-event-fallback')

  registerUiCopy({
    key: jumpKey,
    order: 10,
    surfaces: ['discussion-event-post-number-title'],
    resolve: ({ postNumber }) => ({
      text: `jump:${postNumber}`,
    }),
  })

  registerUiCopy({
    key: approvedKey,
    order: 20,
    surfaces: ['discussion-event-approved-label'],
    resolve: () => ({
      text: 'event approved',
    }),
  })

  registerUiCopy({
    key: postHiddenKey,
    order: 30,
    surfaces: ['post-event-hidden-label'],
    resolve: ({ isHidden, targetPostNumber }) => ({
      text: `${isHidden ? 'hide' : 'show'}:${targetPostNumber}`,
    }),
  })

  registerUiCopy({
    key: fallbackKey,
    order: 40,
    surfaces: ['discussion-generic-event-fallback-label'],
    resolve: () => ({
      text: 'generic event',
    }),
  })

  const jumpResult = getUiCopy({
    surface: 'discussion-event-post-number-title',
    postNumber: 8,
  })
  const approvedResult = getUiCopy({
    surface: 'discussion-event-approved-label',
  })
  const postHiddenResult = getUiCopy({
    surface: 'post-event-hidden-label',
    isHidden: true,
    targetPostNumber: 15,
  })
  const fallbackResult = getUiCopy({
    surface: 'discussion-generic-event-fallback-label',
  })

  assert.equal(jumpResult.key, jumpKey)
  assert.equal(jumpResult.text, 'jump:8')
  assert.equal(approvedResult.key, approvedKey)
  assert.equal(approvedResult.text, 'event approved')
  assert.equal(postHiddenResult.key, postHiddenKey)
  assert.equal(postHiddenResult.text, 'hide:15')
  assert.equal(fallbackResult.key, fallbackKey)
  assert.equal(fallbackResult.text, 'generic event')
})

test('ui copy resolves discussion post item and list meta copy', () => {
  const postTitleKey = uniqueKey('ui-post-title')
  const replyKey = uniqueKey('ui-post-reply')
  const createdKey = uniqueKey('ui-list-created')
  const lastPostedKey = uniqueKey('ui-list-last-posted')

  registerUiCopy({
    key: postTitleKey,
    order: 10,
    surfaces: ['discussion-post-number-title'],
    resolve: ({ postNumber }) => ({
      text: `post:${postNumber}`,
    }),
  })

  registerUiCopy({
    key: replyKey,
    order: 20,
    surfaces: ['discussion-post-reply-action'],
    resolve: () => ({
      text: 'reply action',
    }),
  })

  registerUiCopy({
    key: createdKey,
    order: 30,
    surfaces: ['discussion-list-item-created-at'],
    resolve: ({ relativeTime }) => ({
      text: `created:${relativeTime}`,
    }),
  })

  registerUiCopy({
    key: lastPostedKey,
    order: 40,
    surfaces: ['discussion-list-item-last-posted-at'],
    resolve: ({ relativeTime }) => ({
      text: `last:${relativeTime}`,
    }),
  })

  const postTitleResult = getUiCopy({
    surface: 'discussion-post-number-title',
    postNumber: 12,
  })
  const replyResult = getUiCopy({
    surface: 'discussion-post-reply-action',
  })
  const createdResult = getUiCopy({
    surface: 'discussion-list-item-created-at',
    relativeTime: '1 小时前',
  })
  const lastPostedResult = getUiCopy({
    surface: 'discussion-list-item-last-posted-at',
    relativeTime: '2 分钟前',
  })

  assert.equal(postTitleResult.key, postTitleKey)
  assert.equal(postTitleResult.text, 'post:12')
  assert.equal(replyResult.key, replyKey)
  assert.equal(replyResult.text, 'reply action')
  assert.equal(createdResult.key, createdKey)
  assert.equal(createdResult.text, 'created:1 小时前')
  assert.equal(lastPostedResult.key, lastPostedKey)
  assert.equal(lastPostedResult.text, 'last:2 分钟前')
})

test('ui copy resolves discussion list toolbar and content copy', () => {
  const sortKey = uniqueKey('ui-sort-label')
  const refreshingKey = uniqueKey('ui-list-refreshing')
  const loadMoreKey = uniqueKey('ui-list-load-more')

  registerUiCopy({
    key: sortKey,
    order: 10,
    surfaces: ['discussion-list-toolbar-sort-label'],
    resolve: ({ code }) => ({
      text: `sort:${code}`,
    }),
  })

  registerUiCopy({
    key: refreshingKey,
    order: 20,
    surfaces: ['discussion-list-refreshing'],
    resolve: () => ({
      text: 'refreshing discussions',
    }),
  })

  registerUiCopy({
    key: loadMoreKey,
    order: 30,
    surfaces: ['discussion-list-load-more'],
    resolve: () => ({
      text: 'load more discussions',
    }),
  })

  const sortResult = getUiCopy({
    surface: 'discussion-list-toolbar-sort-label',
    code: 'top',
  })
  const refreshingResult = getUiCopy({
    surface: 'discussion-list-refreshing',
  })
  const loadMoreResult = getUiCopy({
    surface: 'discussion-list-load-more',
  })

  assert.equal(sortResult.key, sortKey)
  assert.equal(sortResult.text, 'sort:top')
  assert.equal(refreshingResult.key, refreshingKey)
  assert.equal(refreshingResult.text, 'refreshing discussions')
  assert.equal(loadMoreResult.key, loadMoreKey)
  assert.equal(loadMoreResult.text, 'load more discussions')
})

test('ui copy resolves discussion list hero and search meta copy', () => {
  const followingKey = uniqueKey('ui-following-hero')
  const searchMetaKey = uniqueKey('ui-search-meta')

  registerUiCopy({
    key: followingKey,
    order: 10,
    surfaces: ['discussion-list-following-hero-description'],
    resolve: () => ({
      text: 'following hero description',
    }),
  })

  registerUiCopy({
    key: searchMetaKey,
    order: 20,
    surfaces: ['search-page-meta-description'],
    resolve: ({ query }) => ({
      text: `meta:${query}`,
    }),
  })

  const followingResult = getUiCopy({
    surface: 'discussion-list-following-hero-description',
  })
  const searchMetaResult = getUiCopy({
    surface: 'search-page-meta-description',
    query: 'Django',
    hasQuery: true,
  })

  assert.equal(followingResult.key, followingKey)
  assert.equal(followingResult.text, 'following hero description')
  assert.equal(searchMetaResult.key, searchMetaKey)
  assert.equal(searchMetaResult.text, 'meta:Django')
})

test('ui copy resolves search stats and result count copy', () => {
  const statsKey = uniqueKey('ui-search-stats')
  const repliesKey = uniqueKey('ui-search-replies')
  const userDiscussionsKey = uniqueKey('ui-search-user-discussions')

  registerUiCopy({
    key: statsKey,
    order: 10,
    surfaces: ['search-page-stats-label'],
    resolve: ({ itemKey }) => ({
      text: `stats:${itemKey}`,
    }),
  })

  registerUiCopy({
    key: repliesKey,
    order: 20,
    surfaces: ['search-discussion-result-replies'],
    resolve: ({ count }) => ({
      text: `replies:${count}`,
    }),
  })

  registerUiCopy({
    key: userDiscussionsKey,
    order: 30,
    surfaces: ['search-user-result-discussions'],
    resolve: ({ count }) => ({
      text: `discussions:${count}`,
    }),
  })

  const statsResult = getUiCopy({
    surface: 'search-page-stats-label',
    itemKey: 'users',
  })
  const repliesResult = getUiCopy({
    surface: 'search-discussion-result-replies',
    count: 8,
  })
  const userDiscussionsResult = getUiCopy({
    surface: 'search-user-result-discussions',
    count: 3,
  })

  assert.equal(statsResult.key, statsKey)
  assert.equal(statsResult.text, 'stats:users')
  assert.equal(repliesResult.key, repliesKey)
  assert.equal(repliesResult.text, 'replies:8')
  assert.equal(userDiscussionsResult.key, userDiscussionsKey)
  assert.equal(userDiscussionsResult.text, 'discussions:3')
})

test('ui copy resolves post composer and search post copy', () => {
  const composerTitleKey = uniqueKey('ui-post-composer-title')
  const draftKey = uniqueKey('ui-post-composer-draft')
  const pendingKey = uniqueKey('ui-post-composer-pending')
  const unknownUserKey = uniqueKey('ui-search-unknown-user')

  registerUiCopy({
    key: composerTitleKey,
    order: 10,
    surfaces: ['post-composer-title'],
    resolve: ({ postNumber }) => ({
      text: `title:${postNumber}`,
    }),
  })

  registerUiCopy({
    key: draftKey,
    order: 20,
    surfaces: ['post-composer-draft-restored'],
    resolve: ({ draftSavedAtText }) => ({
      text: `draft:${draftSavedAtText}`,
    }),
  })

  registerUiCopy({
    key: pendingKey,
    order: 30,
    surfaces: ['post-composer-create-pending-title'],
    resolve: () => ({
      text: 'pending create',
    }),
  })

  registerUiCopy({
    key: unknownUserKey,
    order: 40,
    surfaces: ['search-result-unknown-user'],
    resolve: () => ({
      text: 'unknown search user',
    }),
  })

  const composerTitleResult = getUiCopy({
    surface: 'post-composer-title',
    postNumber: 7,
  })
  const draftResult = getUiCopy({
    surface: 'post-composer-draft-restored',
    hasDraftSavedAt: true,
    draftSavedAtText: '昨天',
  })
  const pendingResult = getUiCopy({
    surface: 'post-composer-create-pending-title',
  })
  const unknownUserResult = getUiCopy({
    surface: 'search-result-unknown-user',
  })

  assert.equal(composerTitleResult.key, composerTitleKey)
  assert.equal(composerTitleResult.text, 'title:7')
  assert.equal(draftResult.key, draftKey)
  assert.equal(draftResult.text, 'draft:昨天')
  assert.equal(pendingResult.key, pendingKey)
  assert.equal(pendingResult.text, 'pending create')
  assert.equal(unknownUserResult.key, unknownUserKey)
  assert.equal(unknownUserResult.text, 'unknown search user')
})

test('ui copy resolves discussion composer copy', () => {
  const headingKey = uniqueKey('ui-discussion-composer-heading')
  const statusKey = uniqueKey('ui-discussion-composer-status')
  const pendingKey = uniqueKey('ui-discussion-composer-pending')

  registerUiCopy({
    key: headingKey,
    order: 10,
    surfaces: ['discussion-composer-heading'],
    resolve: ({ isEditingDiscussion }) => ({
      text: isEditingDiscussion ? 'edit discussion' : 'create discussion',
    }),
  })

  registerUiCopy({
    key: statusKey,
    order: 20,
    surfaces: ['discussion-composer-status-text'],
    resolve: ({ selectedTagName }) => ({
      text: `status:${selectedTagName}`,
    }),
  })

  registerUiCopy({
    key: pendingKey,
    order: 30,
    surfaces: ['discussion-composer-create-pending-title'],
    resolve: () => ({
      text: 'discussion pending',
    }),
  })

  const headingResult = getUiCopy({
    surface: 'discussion-composer-heading',
    isEditingDiscussion: true,
  })
  const statusResult = getUiCopy({
    surface: 'discussion-composer-status-text',
    selectedTagName: '产品 / 发布',
  })
  const pendingResult = getUiCopy({
    surface: 'discussion-composer-create-pending-title',
  })

  assert.equal(headingResult.key, headingKey)
  assert.equal(headingResult.text, 'edit discussion')
  assert.equal(statusResult.key, statusKey)
  assert.equal(statusResult.text, 'status:产品 / 发布')
  assert.equal(pendingResult.key, pendingKey)
  assert.equal(pendingResult.text, 'discussion pending')
})

test('composer hosts resolve extension-owned components by order and module state', () => {
  const firstKey = uniqueKey('composer-host-first')
  const hiddenKey = uniqueKey('composer-host-hidden')
  const secondKey = uniqueKey('composer-host-second')

  registerComposerHost({
    key: secondKey,
    moduleId: 'posts',
    order: 20,
    component: 'PostComposerHost',
  })
  registerComposerHost({
    key: firstKey,
    moduleId: 'discussions',
    order: 10,
    component: 'DiscussionComposerHost',
    componentProps: ({ requestId }) => ({ requestId }),
  })
  registerComposerHost({
    key: hiddenKey,
    moduleId: 'disabled-composer',
    order: 5,
    component: 'HiddenComposerHost',
  })

  const hosts = getComposerHosts({
    requestId: 42,
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== 'disabled-composer'
      },
    },
  })

  assert.equal(hosts.some(item => item.key === hiddenKey), false)
  assert.equal(hosts[0].key, firstKey)
  assert.equal(hosts[0].component, 'DiscussionComposerHost')
  assert.deepEqual(hosts[0].componentProps, { requestId: 42 })
  assert.equal(hosts[1].key, secondKey)
})

test('composer draft meta returns ordered visible items', () => {
  const discussionKey = uniqueKey('composer-draft-discussion')
  const postKey = uniqueKey('composer-draft-post')

  registerComposerDraftMeta({
    key: discussionKey,
    order: 30,
    isVisible: ({ type, minimized }) => type === 'discussion' && !minimized,
    resolve: ({ draftSavedAt }) => ({
      label: '草稿',
      value: `discussion:${draftSavedAt}`,
    }),
  })

  registerComposerDraftMeta({
    key: postKey,
    order: 10,
    isVisible: ({ type, minimized }) => type === 'post' && !minimized,
    resolve: ({ draftSavedAt }) => ({
      label: '草稿',
      value: `post:${draftSavedAt}`,
    }),
  })

  const postItems = getComposerDraftMeta({
    type: 'post',
    minimized: false,
    draftSavedAt: '10:00',
  })
  const hiddenItems = getComposerDraftMeta({
    type: 'discussion',
    minimized: true,
    draftSavedAt: '11:00',
  })

  assert.equal(postItems.length > 0, true)
  assert.equal(postItems[0].key, postKey)
  assert.equal(postItems[0].value, 'post:10:00')
  assert.deepEqual(hiddenItems, [])
})

test('composer fields and payload contributors are extension-owned and ordered', async () => {
  const fieldKey = uniqueKey('composer-field')
  const contributorFirstKey = uniqueKey('composer-payload-first')
  const contributorSecondKey = uniqueKey('composer-payload-second')

  registerComposerField({
    key: fieldKey,
    moduleId: 'tags',
    order: 10,
    isVisible: ({ type }) => type === 'discussion',
    resolve: ({ extensionState }) => ({
      component: 'TagField',
      statusText: extensionState?.tags?.selectedTagLabel || '',
    }),
  })

  registerComposerPayloadContributor({
    key: contributorSecondKey,
    moduleId: 'tags',
    order: 20,
    contribute({ payload }) {
      return {
        ...payload,
        data: {
          ...payload.data,
          relationships: {
            ...payload.data.relationships,
            secondary: { data: [{ type: 'tag', id: '2' }] },
          },
        },
      }
    },
  })

  registerComposerPayloadContributor({
    key: contributorFirstKey,
    moduleId: 'tags',
    order: 10,
    contribute({ payload }) {
      return {
        ...payload,
        data: {
          ...payload.data,
          relationships: {
            ...payload.data.relationships,
            primary: { data: [{ type: 'tag', id: '1' }] },
          },
        },
      }
    },
  })

  const context = {
    type: 'discussion',
    extensionState: {
      tags: { selectedTagLabel: '公告' },
    },
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'tags'
      },
    },
  }
  const fields = getComposerFields(context)
  const payload = await runComposerPayloadContributors({
    data: {
      type: 'discussion',
      relationships: {},
    },
  }, context)

  assert.equal(fields.some(item => item.key === fieldKey), true)
  assert.equal(fields.find(item => item.key === fieldKey).component, 'TagField')
  assert.equal(fields.find(item => item.key === fieldKey).statusText, '公告')
  assert.deepEqual(Object.keys(payload.data.relationships), ['primary', 'secondary'])
  assert.deepEqual(getComposerFields({
    ...context,
    forumStore: { isModuleEnabled: () => false },
  }).some(item => item.key === fieldKey), false)
})

test('composer initial state contributors merge ordered extension state', async () => {
  const firstKey = uniqueKey('composer-initial-first')
  const secondKey = uniqueKey('composer-initial-second')
  const disabledKey = uniqueKey('composer-initial-disabled')

  registerComposerInitialState({
    key: secondKey,
    moduleId: 'tags',
    order: 20,
    contribute({ initialState }) {
      return {
        discussionTitle: `${initialState.discussionTitle}:tagged`,
        extensions: {
          tags: {
            secondaryTagId: '2',
          },
        },
      }
    },
  })

  registerComposerInitialState({
    key: firstKey,
    moduleId: 'tags',
    order: 10,
    contribute() {
      return {
        extensions: {
          tags: {
            primaryTagId: '1',
          },
        },
      }
    },
  })

  registerComposerInitialState({
    key: disabledKey,
    moduleId: 'disabled-module',
    order: 5,
    contribute() {
      return {
        extensions: {
          disabled: {
            touched: true,
          },
        },
      }
    },
  })

  const state = await runComposerInitialStateContributors({
    discussionTitle: '公告',
    extensions: {
      polls: {
        question: '选择？',
      },
    },
  }, {
    type: 'discussion',
    submitKind: 'edit-discussion',
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId === 'tags'
      },
    },
  })

  assert.equal(state.discussionTitle, '公告:tagged')
  assert.deepEqual(state.extensions, {
    polls: {
      question: '选择？',
    },
    tags: {
      primaryTagId: '1',
      secondaryTagId: '2',
    },
  })
})

test('composer submit success handlers run in order and respect visibility', async () => {
  const calls = []
  const firstKey = uniqueKey('composer-submit-success-first')
  const secondKey = uniqueKey('composer-submit-success-second')

  registerComposerSubmitSuccess({
    key: firstKey,
    order: 20,
    isVisible: ({ type }) => type === 'discussion',
    async run({ data }) {
      calls.push(`second:${data.id}`)
    },
  })

  registerComposerSubmitSuccess({
    key: secondKey,
    order: 10,
    isVisible: ({ mode }) => mode === 'create',
    async run({ data }) {
      calls.push(`first:${data.id}`)
    },
  })

  const handledCount = await runComposerSubmitSuccess({
    type: 'discussion',
    mode: 'create',
    data: { id: 7 },
  })

  const skippedCount = await runComposerSubmitSuccess({
    type: 'post',
    mode: 'edit',
    data: { id: 9 },
  })

  assert.equal(handledCount, 2)
  assert.equal(skippedCount, 0)
  assert.deepEqual(calls, ['first:7', 'second:7'])
})

test('composer autocomplete providers resolve by order, surface and module state', () => {
  const firstKey = uniqueKey('composer-autocomplete-first')
  const secondKey = uniqueKey('composer-autocomplete-second')
  const hiddenKey = uniqueKey('composer-autocomplete-hidden')

  registerComposerAutocompleteProvider({
    key: firstKey,
    moduleId: 'mentions',
    order: 20,
    renderer: 'mention',
    surfaces: ['composer-body'],
    detect: () => ({ query: 'b' }),
    search: () => [{ id: 2, username: 'beta' }],
    replacement: ({ item }) => `@${item.username} `,
  })

  registerComposerAutocompleteProvider({
    key: secondKey,
    moduleId: 'emoji',
    order: 10,
    renderer: 'emoji',
    surfaces: ['composer-body'],
    detect: () => ({ query: 'a' }),
    search: () => [{ id: 'smile', emoji: '🙂' }],
    replacement: ({ item }) => item.emoji,
  })

  registerComposerAutocompleteProvider({
    key: hiddenKey,
    moduleId: 'disabled-module',
    order: 5,
    renderer: 'hidden',
    surfaces: ['composer-body'],
  })

  const providers = getComposerAutocompleteProviders({
    surface: 'composer-body',
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== 'disabled-module'
      },
    },
  })

  assert.deepEqual(
    providers.filter(item => [firstKey, secondKey, hiddenKey].includes(item.key)).map(item => item.key),
    [secondKey, firstKey]
  )
  assert.equal(providers.find(item => item.key === firstKey).renderer, 'mention')
  assert.equal(providers.find(item => item.key === secondKey).replacement({ item: { emoji: '🙂' } }), '🙂')
  assert.deepEqual(getComposerAutocompleteProviders({
    surface: 'other-surface',
  }).filter(item => [firstKey, secondKey, hiddenKey].includes(item.key)), [])
})

test('composer upload handler resolves extension-owned uploader by module state', () => {
  const handlerKey = uniqueKey('composer-upload-handler')
  const hiddenKey = uniqueKey('composer-upload-hidden')

  registerComposerUploadHandler({
    key: hiddenKey,
    moduleId: 'disabled-uploads',
    order: 5,
    upload: () => ({ markdown: 'hidden' }),
  })

  registerComposerUploadHandler({
    key: handlerKey,
    moduleId: 'uploads',
    order: 10,
    upload: ({ fileName }) => ({ markdown: `[${fileName}](/file)` }),
  })

  const handler = getComposerUploadHandler({
    fileName: 'report.pdf',
    forumStore: {
      isModuleEnabled(moduleId) {
        return moduleId !== 'disabled-uploads'
      },
    },
  })

  assert.equal(handler.key, handlerKey)
  assert.deepEqual(handler.upload({ fileName: 'report.pdf' }), { markdown: '[report.pdf](/file)' })
  assert.equal(getComposerUploadHandler({
    forumStore: { isModuleEnabled: () => false },
  })?.key === handlerKey, false)
})

test('composer preview transformers run in order and pass transformed html forward', async () => {
  const firstKey = uniqueKey('composer-preview-transform-first')
  const secondKey = uniqueKey('composer-preview-transform-second')

  registerComposerPreviewTransformer({
    key: firstKey,
    order: 10,
    async transform({ html }) {
      return {
        html: `${html}<strong>first</strong>`,
      }
    },
  })

  registerComposerPreviewTransformer({
    key: secondKey,
    order: 20,
    async transform({ html }) {
      return `${html}<em>second</em>`
    },
  })

  const result = await runComposerPreviewTransformers({
    html: '<p>base</p>',
  })

  assert.equal(result.html, '<p>base</p><strong>first</strong><em>second</em>')
})

test('ui copy resolves profile feedback copy', () => {
  const settingsKey = uniqueKey('ui-profile-settings')
  const passwordKey = uniqueKey('ui-profile-password')
  const avatarKey = uniqueKey('ui-profile-avatar')

  registerUiCopy({
    key: settingsKey,
    order: 10,
    surfaces: ['profile-settings-save-success'],
    resolve: ({ emailChanged, email }) => ({
      text: emailChanged ? `settings:${email}` : 'settings:plain',
    }),
  })

  registerUiCopy({
    key: passwordKey,
    order: 20,
    surfaces: ['profile-password-mismatch-error'],
    resolve: () => ({
      text: 'password mismatch',
    }),
  })

  registerUiCopy({
    key: avatarKey,
    order: 30,
    surfaces: ['profile-avatar-upload-error-title'],
    resolve: () => ({
      text: 'avatar upload failed',
    }),
  })

  const settingsResult = getUiCopy({
    surface: 'profile-settings-save-success',
    emailChanged: true,
    email: 'a@b.com',
  })
  const passwordResult = getUiCopy({
    surface: 'profile-password-mismatch-error',
  })
  const avatarResult = getUiCopy({
    surface: 'profile-avatar-upload-error-title',
  })

  assert.equal(settingsResult.key, settingsKey)
  assert.equal(settingsResult.text, 'settings:a@b.com')
  assert.equal(passwordResult.key, passwordKey)
  assert.equal(passwordResult.text, 'password mismatch')
  assert.equal(avatarResult.key, avatarKey)
  assert.equal(avatarResult.text, 'avatar upload failed')
})

test('ui copy resolves profile settings and security section copy', () => {
  const settingsSectionKey = uniqueKey('ui-profile-settings-section')
  const preferenceGroupKey = uniqueKey('ui-profile-preference-group')
  const securitySectionKey = uniqueKey('ui-profile-security-section')
  const passwordLabelKey = uniqueKey('ui-profile-password-label')

  registerUiCopy({
    key: settingsSectionKey,
    order: 10,
    surfaces: ['profile-settings-section-title'],
    resolve: () => ({
      text: 'settings section',
    }),
  })

  registerUiCopy({
    key: preferenceGroupKey,
    order: 20,
    surfaces: ['profile-preferences-group-label'],
    resolve: ({ category }) => ({
      text: `group:${category}`,
    }),
  })

  registerUiCopy({
    key: securitySectionKey,
    order: 30,
    surfaces: ['profile-security-section-title'],
    resolve: () => ({
      text: 'security section',
    }),
  })

  registerUiCopy({
    key: passwordLabelKey,
    order: 40,
    surfaces: ['profile-security-new-password-label'],
    resolve: () => ({
      text: 'new password label',
    }),
  })

  const settingsSectionResult = getUiCopy({
    surface: 'profile-settings-section-title',
  })
  const preferenceGroupResult = getUiCopy({
    surface: 'profile-preferences-group-label',
    category: 'behavior',
  })
  const securitySectionResult = getUiCopy({
    surface: 'profile-security-section-title',
  })
  const passwordLabelResult = getUiCopy({
    surface: 'profile-security-new-password-label',
  })

  assert.equal(settingsSectionResult.key, settingsSectionKey)
  assert.equal(settingsSectionResult.text, 'settings section')
  assert.equal(preferenceGroupResult.key, preferenceGroupKey)
  assert.equal(preferenceGroupResult.text, 'group:behavior')
  assert.equal(securitySectionResult.key, securitySectionKey)
  assert.equal(securitySectionResult.text, 'security section')
  assert.equal(passwordLabelResult.key, passwordLabelKey)
  assert.equal(passwordLabelResult.text, 'new password label')
})

test('ui copy resolves auth session modal copy', () => {
  const titleKey = uniqueKey('ui-auth-title')
  const fieldErrorKey = uniqueKey('ui-auth-field-error')
  const turnstileErrorKey = uniqueKey('ui-auth-turnstile-error')

  registerUiCopy({
    key: titleKey,
    order: 10,
    surfaces: ['auth-session-title'],
    resolve: ({ mode }) => ({
      text: `title:${mode}`,
    }),
  })

  registerUiCopy({
    key: fieldErrorKey,
    order: 20,
    surfaces: ['auth-register-field-error'],
    resolve: ({ field, message }) => ({
      text: `${field}=>${message}`,
    }),
  })

  registerUiCopy({
    key: turnstileErrorKey,
    order: 30,
    surfaces: ['auth-turnstile-load-error'],
    resolve: () => ({
      text: 'turnstile load failed',
    }),
  })

  const titleResult = getUiCopy({
    surface: 'auth-session-title',
    mode: 'register',
  })
  const fieldErrorResult = getUiCopy({
    surface: 'auth-register-field-error',
    field: '邮箱',
    message: 'invalid',
  })
  const turnstileErrorResult = getUiCopy({
    surface: 'auth-turnstile-load-error',
  })

  assert.equal(titleResult.key, titleKey)
  assert.equal(titleResult.text, 'title:register')
  assert.equal(fieldErrorResult.key, fieldErrorKey)
  assert.equal(fieldErrorResult.text, '邮箱=>invalid')
  assert.equal(turnstileErrorResult.key, turnstileErrorKey)
  assert.equal(turnstileErrorResult.text, 'turnstile load failed')
})

test('discussion action runtime confirms then dispatches to handler map', async () => {
  let confirmedPayload = null
  let handlerCalls = 0
  const discussionActionKey = uniqueKey('discussion-runtime-delete')

  registerDiscussionAction({
    key: discussionActionKey,
    resolve: () => ({
      key: discussionActionKey,
      label: '删除讨论',
      tone: 'danger',
      confirm: {
        confirmText: '删除',
      },
    }),
  })

  const item = resolveDiscussionAction(discussionActionKey, {})

  const result = await runDiscussionAction(item, {
    discussionActionHandlers: {
      [discussionActionKey]: async () => {
        handlerCalls += 1
      },
    },
    modalStore: {
      confirm: async payload => {
        confirmedPayload = payload
        return true
      },
    },
  })

  assert.equal(result, true)
  assert.equal(handlerCalls, 1)
  assert.equal(confirmedPayload.confirmText, '删除')
  assert.equal(confirmedPayload.tone, 'danger')
})

test('discussion action runtime dispatches registered extension handlers', async () => {
  const handlerKey = uniqueKey('discussion-runtime-extension-handler')
  const moduleId = 'discussion-actions-demo'
  const calls = []

  registerDiscussionActionHandler({
    key: handlerKey,
    moduleId,
    async handle(context) {
      calls.push({
        action: context.action,
        discussionId: context.discussion?.id,
        itemKey: context.item?.key,
      })
    },
  })

  const hiddenWhenDisabled = getDiscussionActionHandler(handlerKey, {
    forumStore: {
      isModuleEnabled: currentModuleId => currentModuleId !== moduleId,
    },
  })
  const visibleWhenEnabled = getDiscussionActionHandler(handlerKey, {
    forumStore: {
      isModuleEnabled: currentModuleId => currentModuleId === moduleId,
    },
  })
  const completed = await runDiscussionAction(
    { key: handlerKey },
    {
      action: handlerKey,
      discussion: { id: 88 },
      forumStore: {
        isModuleEnabled: currentModuleId => currentModuleId === moduleId,
      },
    }
  )

  assert.equal(hiddenWhenDisabled, null)
  assert.equal(visibleWhenEnabled.key, handlerKey)
  assert.equal(completed, true)
  assert.deepEqual(calls, [
    {
      action: handlerKey,
      discussionId: 88,
      itemKey: handlerKey,
    },
  ])
})

test('post action runtime prefers explicit action key and respects cancellation', async () => {
  let handlerCalls = 0
  const postActionKey = uniqueKey('post-runtime-delete')

  registerPostAction({
    key: postActionKey,
    resolve: () => ({
      key: postActionKey,
      label: '删除回复',
      tone: 'danger',
      confirm: {
        confirmText: '删除',
      },
    }),
  })

  const postItem = {
    ...getPostActions({}).find(item => item.key === postActionKey),
    action: 'custom-delete-post',
  }

  const cancelled = await runPostAction(postItem, {
    modalStore: {
      confirm: async () => false,
    },
    postActionHandlers: {
      'custom-delete-post': async () => {
        handlerCalls += 1
      },
    },
  })

  const completed = await runPostAction(postItem, {
    modalStore: {
      confirm: async () => true,
    },
    postActionHandlers: {
      'custom-delete-post': async () => {
        handlerCalls += 1
      },
    },
  })

  assert.equal(cancelled, false)
  assert.equal(completed, true)
  assert.equal(handlerCalls, 1)
})

test('post action runtime dispatches registered extension handlers', async () => {
  const handlerKey = uniqueKey('post-runtime-extension-handler')
  const moduleId = 'post-actions-demo'
  const calls = []

  registerPostActionHandler({
    key: handlerKey,
    moduleId,
    async handle(context) {
      calls.push({
        action: context.action,
        postId: context.post?.id,
        itemKey: context.item?.key,
      })
    },
  })

  const hiddenWhenDisabled = getPostActionHandler(handlerKey, {
    forumStore: {
      isModuleEnabled: currentModuleId => currentModuleId !== moduleId,
    },
  })
  const visibleWhenEnabled = getPostActionHandler(handlerKey, {
    forumStore: {
      isModuleEnabled: currentModuleId => currentModuleId === moduleId,
    },
  })
  const completed = await runPostAction(
    { key: handlerKey },
    {
      action: handlerKey,
      forumStore: {
        isModuleEnabled: currentModuleId => currentModuleId === moduleId,
      },
      post: { id: 77 },
    }
  )

  assert.equal(hiddenWhenDisabled, null)
  assert.equal(visibleWhenEnabled.key, handlerKey)
  assert.equal(completed, true)
  assert.deepEqual(calls, [
    {
      action: handlerKey,
      postId: 77,
      itemKey: handlerKey,
    },
  ])
})
