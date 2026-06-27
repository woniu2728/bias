import {
  clearRegistryExtensions,
  isRegisteredItemEnabled,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '../common/contributionRegistry.js'
import { getFrontendRegistrySlot } from '../common/frontendRegistrySlots.js'

const forumNavItems = getFrontendRegistrySlot('forum.navItems')
const forumSidebarSections = getFrontendRegistrySlot('forum.sidebarSections')
const headerItems = getFrontendRegistrySlot('forum.headerItems')
const forumNavSections = getFrontendRegistrySlot('forum.navSections')
const composerTools = getFrontendRegistrySlot('composer.tools')
const composerFields = getFrontendRegistrySlot('composer.fields')
const composerNotices = getFrontendRegistrySlot('composer.notices')
const composerSubmitGuards = getFrontendRegistrySlot('composer.submitGuards')
const composerPayloadContributors = getFrontendRegistrySlot('composer.payloadContributors')
const composerInitialStateContributors = getFrontendRegistrySlot('composer.initialStateContributors')
const composerSecondaryActions = getFrontendRegistrySlot('composer.secondaryActions')
const composerStatusItems = getFrontendRegistrySlot('composer.statusItems')
const composerDraftMetaItems = getFrontendRegistrySlot('composer.draftMetaItems')
const composerSubmitSuccessHandlers = getFrontendRegistrySlot('composer.submitSuccessHandlers')
const composerAutocompleteProviders = getFrontendRegistrySlot('composer.autocompleteProviders')
const composerPreviewTransformers = getFrontendRegistrySlot('composer.previewTransformers')
const composerHosts = getFrontendRegistrySlot('composer.hosts')
const composerUploadHandlers = getFrontendRegistrySlot('composer.uploadHandlers')
const heroMetaItems = getFrontendRegistrySlot('forum.heroMetaItems')
const feedbackNotes = getFrontendRegistrySlot('forum.feedbackNotes')
const emptyStates = getFrontendRegistrySlot('forum.emptyStates')
const pageStates = getFrontendRegistrySlot('forum.pageStates')
const stateBlocks = getFrontendRegistrySlot('forum.stateBlocks')
const uiCopies = getFrontendRegistrySlot('forum.uiCopies')
const forumRuntimeHooks = getFrontendRegistrySlot('forum.runtimeHooks')
const discussionListContextItems = getFrontendRegistrySlot('discussions.listContexts')
const discussionListRequestItems = getFrontendRegistrySlot('discussions.listRequests')
const discussionListHeroItems = getFrontendRegistrySlot('discussions.listHeroes')
const discussionActionItems = getFrontendRegistrySlot('discussions.actions')
const discussionActionHandlers = getFrontendRegistrySlot('discussions.actionHandlers')
const discussionBadges = getFrontendRegistrySlot('discussions.badges')
const discussionStateBadges = getFrontendRegistrySlot('discussions.stateBadges')
const discussionPresentationItems = getFrontendRegistrySlot('discussions.presentation')
const discussionReplyStates = getFrontendRegistrySlot('discussions.replyStates')
const discussionReviewBanners = getFrontendRegistrySlot('discussions.reviewBanners')
const startDiscussionProviders = getFrontendRegistrySlot('discussions.startProviders')
const postActionItems = getFrontendRegistrySlot('posts.actions')
const postActionHandlers = getFrontendRegistrySlot('posts.actionHandlers')
const postStateBadges = getFrontendRegistrySlot('posts.stateBadges')
const postReviewBanners = getFrontendRegistrySlot('posts.reviewBanners')
const postFlagPanels = getFrontendRegistrySlot('posts.flagPanels')
const postTypeDefinitions = getFrontendRegistrySlot('posts.types')
const fallbackPostTypeDefinition = {
  type: 'event',
  label: '系统事件',
  component: null,
  order: 999,
  isDefault: false,
  isFallback: true,
}
const searchSources = getFrontendRegistrySlot('search.sources')
const searchModalProviders = getFrontendRegistrySlot('search.modalProviders')
const searchModalSections = getFrontendRegistrySlot('search.modalSections')
const profilePanels = getFrontendRegistrySlot('users.profilePanels')
const userBadges = getFrontendRegistrySlot('users.badges')
const authModalProviders = getFrontendRegistrySlot('users.authModalProviders')
const authChallengeProviders = getFrontendRegistrySlot('users.authChallengeProviders')
const notificationRenderers = getFrontendRegistrySlot('notifications.renderers')
const forumRealtimeEvents = getFrontendRegistrySlot('realtime.forumEvents')

const registryTargets = [
  forumNavItems,
  forumSidebarSections,
  headerItems,
  forumNavSections,
  composerTools,
  composerFields,
  composerNotices,
  composerSubmitGuards,
  composerPayloadContributors,
  composerInitialStateContributors,
  composerSecondaryActions,
  composerStatusItems,
  composerDraftMetaItems,
  composerSubmitSuccessHandlers,
  composerAutocompleteProviders,
  composerPreviewTransformers,
  composerHosts,
  composerUploadHandlers,
  heroMetaItems,
  feedbackNotes,
  emptyStates,
  pageStates,
  stateBlocks,
  uiCopies,
  forumRuntimeHooks,
  discussionListContextItems,
  discussionListRequestItems,
  discussionListHeroItems,
  discussionActionItems,
  discussionActionHandlers,
  discussionBadges,
  discussionStateBadges,
  discussionPresentationItems,
  discussionReplyStates,
  discussionReviewBanners,
  startDiscussionProviders,
  postActionItems,
  postActionHandlers,
  postStateBadges,
  postReviewBanners,
  postFlagPanels,
  postTypeDefinitions,
  searchSources,
  searchModalProviders,
  searchModalSections,
  profilePanels,
  userBadges,
  authModalProviders,
  authChallengeProviders,
  notificationRenderers,
  forumRealtimeEvents,
]

export function clearForumRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
}

export function registerForumNavItem(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(forumNavItems, normalizedItem.key, normalizedItem)
}

export function registerForumNavSection(section) {
  const normalizedSection = {
    order: 100,
    ...section,
  }
  return upsertByKey(forumNavSections, normalizedSection.key, normalizedSection)
}

export function registerForumSidebarSection(section) {
  const normalizedSection = normalizeRegisteredItem(section)
  return upsertByKey(forumSidebarSections, normalizedSection.key, normalizedSection)
}

export function getForumSidebarSections(context = {}) {
  return orderedRegisteredItems(forumSidebarSections)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionListContext(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionListContextItems, normalizedItem.key, normalizedItem)
}

export function getDiscussionListContexts(context = {}) {
  return orderedRegisteredItems(discussionListContextItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionListRequest(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionListRequestItems, normalizedItem.key, normalizedItem)
}

export function getDiscussionListRequests(context = {}) {
  return orderedRegisteredItems(discussionListRequestItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionListHero(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionListHeroItems, normalizedItem.key, normalizedItem)
}

export function getDiscussionListHero(context = {}) {
  return orderedRegisteredItems(discussionListHeroItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)[0] || null
}

export function getForumNavItems(context = {}) {
  return orderedRegisteredItems(forumNavItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function getForumNavSections(context = {}) {
  const items = getForumNavItems(context)
  const sectionMap = new Map(
    orderedRegisteredItems(forumNavSections)
      .map(section => [section.key, { ...section, items: [] }])
  )

  if (!sectionMap.has('primary')) {
    sectionMap.set('primary', { key: 'primary', title: '', order: 10, items: [] })
  }

  for (const item of items) {
    const sectionKey = item.section || 'primary'
    if (!sectionMap.has(sectionKey)) {
      sectionMap.set(sectionKey, { key: sectionKey, title: '', order: 100, items: [] })
    }
    sectionMap.get(sectionKey).items.push(item)
  }

  return [...sectionMap.values()]
    .filter(section => section.items.length > 0)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(section => ({
      ...section,
      items: section.items.sort((left, right) => (left.order || 100) - (right.order || 100)),
    }))
}

export function registerDiscussionAction(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionActionItems, normalizedItem.key, normalizedItem)
}

export function registerDiscussionActionHandler(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionActionHandlers, normalizedItem.key, normalizedItem)
}

export function getDiscussionActionHandler(actionKey, context = {}) {
  const normalizedActionKey = String(actionKey || '').trim()
  if (!normalizedActionKey) {
    return null
  }
  return orderedRegisteredItems(discussionActionHandlers)
    .filter(item => String(item.key || '') === normalizedActionKey)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.handle === 'function') || null
}

export function getDiscussionActions(context = {}) {
  return orderedRegisteredItems(discussionActionItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostAction(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postActionItems, normalizedItem.key, normalizedItem)
}

export function registerPostActionHandler(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postActionHandlers, normalizedItem.key, normalizedItem)
}

export function getPostActionHandler(actionKey, context = {}) {
  const normalizedActionKey = String(actionKey || '').trim()
  if (!normalizedActionKey) {
    return null
  }
  return orderedRegisteredItems(postActionHandlers)
    .filter(item => String(item.key || '') === normalizedActionKey)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.handle === 'function') || null
}

export function getPostActions(context = {}) {
  return orderedRegisteredItems(postActionItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionMenuItem(factory) {
  return registerDiscussionAction({
    key: `external-discussion-action-${Date.now()}-${Math.random()}`,
    isVisible: context => Boolean(factory(context)),
    resolve: factory,
  })
}

export function getDiscussionMenuItems(context = {}) {
  return getDiscussionActions(context)
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

export function registerPostMenuItem(factory) {
  return registerPostAction({
    key: `external-post-action-${Date.now()}-${Math.random()}`,
    isVisible: context => Boolean(factory(context)),
    resolve: factory,
  })
}

export function getPostMenuItems(context = {}) {
  return getPostActions(context)
    .filter(Boolean)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

export function resolveDiscussionAction(actionKey, context = {}) {
  return getDiscussionActions(context).find(item => item.key === actionKey) || null
}

export function resolvePostAction(actionKey, context = {}) {
  return getPostActions(context).find(item => item.key === actionKey) || null
}

export async function runDiscussionAction(item, context = {}) {
  return runRegisteredAction(item, context, {
    handlerKey: 'discussionActionHandlers',
    getHandler: getDiscussionActionHandler,
  })
}

export async function runPostAction(item, context = {}) {
  return runRegisteredAction(item, context, {
    handlerKey: 'postActionHandlers',
    getHandler: getPostActionHandler,
  })
}

async function runRegisteredAction(item, context = {}, { handlerKey = '', getHandler = null } = {}) {
  if (!item || item.disabled) {
    return false
  }

  const modalStore = context.modalStore
  if (item.confirm && modalStore?.confirm) {
    const confirmed = await modalStore.confirm({
      title: item.confirm.title || item.label || getConfirmationText('discussion-action-confirm-title', '确认操作'),
      message: item.confirm.message || getConfirmationText('discussion-action-confirm-message', '确定继续执行这个操作吗？'),
      confirmText: item.confirm.confirmText || getConfirmationText('discussion-action-confirm-default', '继续'),
      cancelText: item.confirm.cancelText || getConfirmationText('discussion-action-confirm-cancel', '取消'),
      tone: item.confirm.tone || item.tone || 'primary',
    })
    if (!confirmed) {
      return false
    }
  }

  if (typeof item.onClick === 'function') {
    await item.onClick({
      ...context,
      item,
    })
    return true
  }

  const handlers = context[handlerKey] || {}
  const actionKey = item.action || item.key
  if (actionKey && typeof handlers[actionKey] === 'function') {
    await handlers[actionKey](item, context)
    return true
  }

  const registeredHandler = typeof getHandler === 'function' ? getHandler(actionKey, context) : null
  if (typeof registeredHandler?.handle === 'function') {
    await registeredHandler.handle({
      ...context,
      item,
    })
    return true
  }

  return false
}

function getConfirmationText(surface, fallback) {
  return getUiCopy({ surface })?.text || fallback
}

export function registerHeaderItem(item) {
  const normalizedItem = normalizeRegisteredItem(item, {
    placement: 'after-search',
  })
  return upsertByKey(headerItems, normalizedItem.key, normalizedItem)
}

export function getHeaderItems(context = {}, placement = '') {
  return orderedRegisteredItems(headerItems)
    .filter(item => !placement || item.placement === placement)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerAuthModalProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(authModalProviders, normalizedItem.key, normalizedItem)
}

export function getAuthModalProvider(context = {}) {
  return orderedRegisteredItems(authModalProviders)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.open === 'function' || item?.component) || null
}

export function registerAuthChallengeProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item, {
    tokenField: 'human_verification_token',
    payloadField: 'human_verification_payload',
  })
  return upsertByKey(authChallengeProviders, normalizedItem.key, normalizedItem)
}

export function getAuthChallengeProvider(context = {}) {
  return orderedRegisteredItems(authChallengeProviders)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => item?.component || typeof item?.buildPayload === 'function') || null
}

export function registerComposerTool(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerTools, normalizedItem.key, normalizedItem)
}

export function getComposerTools(context = {}) {
  return orderedRegisteredItems(composerTools)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerField(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerFields, normalizedItem.key, normalizedItem)
}

export function getComposerFields(context = {}) {
  return orderedRegisteredItems(composerFields)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerNotice(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerNotices, normalizedItem.key, normalizedItem)
}

export function getComposerNotices(context = {}) {
  return orderedRegisteredItems(composerNotices)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerSubmitGuard(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerSubmitGuards, normalizedItem.key, normalizedItem)
}

export function registerComposerPayloadContributor(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerPayloadContributors, normalizedItem.key, normalizedItem)
}

export function registerComposerInitialState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerInitialStateContributors, normalizedItem.key, normalizedItem)
}

export function registerComposerSecondaryAction(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerSecondaryActions, normalizedItem.key, normalizedItem)
}

export function getComposerSecondaryActions(context = {}) {
  return orderedRegisteredItems(composerSecondaryActions)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerStatusItem(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerStatusItems, normalizedItem.key, normalizedItem)
}

export function getComposerStatusItems(context = {}) {
  return orderedRegisteredItems(composerStatusItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerDraftMeta(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerDraftMetaItems, normalizedItem.key, normalizedItem)
}

export function getComposerDraftMeta(context = {}) {
  return orderedRegisteredItems(composerDraftMetaItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerSubmitSuccess(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerSubmitSuccessHandlers, normalizedItem.key, normalizedItem)
}

export function registerComposerAutocompleteProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerAutocompleteProviders, normalizedItem.key, normalizedItem)
}

export function getComposerAutocompleteProviders(context = {}) {
  return orderedRegisteredItems(composerAutocompleteProviders)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerPreviewTransformer(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerPreviewTransformers, normalizedItem.key, normalizedItem)
}

export function registerComposerHost(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  if (!normalizedItem.component) {
    return null
  }
  return upsertByKey(composerHosts, normalizedItem.key, normalizedItem)
}

export function getComposerHosts(context = {}) {
  return orderedRegisteredItems(composerHosts)
    .map(item => resolveRegisteredItem(item, context))
    .filter(item => item?.component)
}

export function registerComposerUploadHandler(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerUploadHandlers, normalizedItem.key, normalizedItem)
}

export function getComposerUploadHandler(context = {}) {
  return orderedRegisteredItems(composerUploadHandlers)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.upload === 'function') || null
}

export function registerProfilePanel(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(profilePanels, normalizedItem.key, normalizedItem)
}

export function getProfilePanels(context = {}) {
  return orderedRegisteredItems(profilePanels)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerNotificationRenderer(item) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  const navigationScope = String(item?.navigationScope || item?.navigation_scope || '').trim()
  const normalizedItem = normalizeRegisteredItem({
    icon: 'fas fa-bell',
    navigationTarget: null,
    navigationScope: 'notifications',
    unreadCountField: '',
    ...item,
    key: item?.key || item?.type,
    type: item?.type || item?.key,
  })
  if (moduleId) {
    normalizedItem.moduleId = moduleId
    normalizedItem.module_id = moduleId
  }
  if (navigationScope) {
    normalizedItem.navigationScope = navigationScope
    normalizedItem.navigation_scope = navigationScope
  }
  return upsertByKey(notificationRenderers, normalizedItem.key, normalizedItem)
}

export function getNotificationRenderers(context = {}) {
  return orderedRegisteredItems(notificationRenderers)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerSearchSource(item) {
  const normalizedItem = normalizeRegisteredItem(item, {
    filterTarget: '',
  })
  return upsertByKey(searchSources, normalizedItem.key, normalizedItem)
}

export function getSearchSources(context = {}) {
  return orderedRegisteredItems(searchSources)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerSearchModalProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(searchModalProviders, normalizedItem.key, normalizedItem)
}

export function getSearchModalProvider(context = {}) {
  return orderedRegisteredItems(searchModalProviders)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.open === 'function' || item?.component) || null
}

export function registerSearchModalSection(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(searchModalSections, normalizedItem.key, normalizedItem)
}

export function getSearchModalSections(context = {}) {
  return orderedRegisteredItems(searchModalSections)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerStartDiscussionProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(startDiscussionProviders, normalizedItem.key, normalizedItem)
}

export function getStartDiscussionProvider(context = {}) {
  return orderedRegisteredItems(startDiscussionProviders)
    .map(item => resolveRegisteredItem(item, context))
    .find(item => typeof item?.start === 'function' || typeof item?.open === 'function' || typeof item?.handle === 'function') || null
}

export function registerUserBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(userBadges, normalizedItem.key, normalizedItem)
}

export function getUserBadges(context = {}) {
  return orderedRegisteredItems(userBadges)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionBadges, normalizedItem.key, normalizedItem)
}

export function getDiscussionBadges(context = {}) {
  return orderedRegisteredItems(discussionBadges)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionStateBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionStateBadges, normalizedItem.key, normalizedItem)
}

export function getDiscussionStateBadges(context = {}) {
  return orderedRegisteredItems(discussionStateBadges)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionPresentation(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionPresentationItems, normalizedItem.key, normalizedItem)
}

export function getDiscussionPresentationItems(context = {}) {
  return orderedRegisteredItems(discussionPresentationItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostStateBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postStateBadges, normalizedItem.key, normalizedItem)
}

export function getPostStateBadges(context = {}) {
  return orderedRegisteredItems(postStateBadges)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostType(definition) {
  const type = String(definition?.code || definition?.type || '').trim()
  if (!type) {
    return null
  }

  const existingDefinition = postTypeDefinitions.find(item => item.type === type)
  const normalizedDefinition = normalizeRegisteredItem({
    order: 100,
    component: existingDefinition?.component || null,
    ...definition,
    component: definition?.component || existingDefinition?.component || null,
    type,
    key: definition?.key || type,
    isDefault: Boolean(definition?.is_default ?? definition?.isDefault),
  })

  return upsertByKey(postTypeDefinitions, normalizedDefinition.type, normalizedDefinition)
}

export function getPostTypeDefinition(type) {
  const normalizedType = String(type || 'comment').trim() || 'comment'
  const exactMatch = postTypeDefinitions.find(item => item.type === normalizedType)
  if (exactMatch) {
    return exactMatch
  }

  if (normalizedType !== 'comment') {
    return {
      ...fallbackPostTypeDefinition,
      type: normalizedType,
      label: normalizedType,
    }
  }

  return (
    postTypeDefinitions.find(item => item.isDefault)
    || postTypeDefinitions[0]
    || null
  )
}

export function syncPostTypes(definitions = []) {
  definitions.forEach((definition, index) => {
    registerPostType({
      ...definition,
      order: Number(definition?.order ?? ((index + 1) * 10)),
    })
  })
}

export function registerHeroMeta(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(heroMetaItems, normalizedItem.key, normalizedItem)
}

export function getHeroMetaItems(context = {}) {
  return orderedRegisteredItems(heroMetaItems)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionReplyState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReplyStates, normalizedItem.key, normalizedItem)
}

export function getDiscussionReplyState(context = {}) {
  return getFirstSurfaceAwareRegistryItem(discussionReplyStates, context)
}

export function registerPostReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postReviewBanners, normalizedItem.key, normalizedItem)
}

export function getPostReviewBanner(context = {}) {
  return getFirstSurfaceAwareRegistryItem(postReviewBanners, context)
}

export function registerDiscussionReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReviewBanners, normalizedItem.key, normalizedItem)
}

export function getDiscussionReviewBanner(context = {}) {
  return getFirstSurfaceAwareRegistryItem(discussionReviewBanners, context)
}

export function registerPostFlagPanel(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postFlagPanels, normalizedItem.key, normalizedItem)
}

export function getPostFlagPanel(context = {}) {
  return getFirstSurfaceAwareRegistryItem(postFlagPanels, context)
}

export function registerFeedbackNote(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(feedbackNotes, normalizedItem.key, normalizedItem)
}

export function getFeedbackNote(context = {}) {
  return getFirstSurfaceAwareRegistryItem(feedbackNotes, context)
}

export function registerEmptyState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(emptyStates, normalizedItem.key, normalizedItem)
}

export function getEmptyState(context = {}) {
  return getFirstSurfaceAwareRegistryItem(emptyStates, context)
}

export function registerPageState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(pageStates, normalizedItem.key, normalizedItem)
}

export function getPageState(context = {}) {
  return getFirstSurfaceAwareRegistryItem(pageStates, context)
}

export function registerStateBlock(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(stateBlocks, normalizedItem.key, normalizedItem)
}

export function getStateBlock(context = {}) {
  return getFirstSurfaceAwareRegistryItem(stateBlocks, context)
}

function getFirstSurfaceAwareRegistryItem(target, context = {}) {
  const resolvedItems = orderedRegisteredItems(target)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)

  if (!resolvedItems.length) {
    return null
  }

  const currentSurface = String(context.surface || '').trim()
  if (!currentSurface) {
    return resolvedItems[0]
  }

  const surfaceSpecificItem = resolvedItems.find(item => Array.isArray(item.surfaces) && item.surfaces.includes(currentSurface))
  return surfaceSpecificItem || resolvedItems[0]
}

export function registerUiCopy(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(uiCopies, normalizedItem.key, normalizedItem)
}

export function createUiTextCopy(key, order, text) {
  return {
    key,
    order,
    surfaces: [key],
    resolve: () => ({ text }),
  }
}

export function registerForumRuntime(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(forumRuntimeHooks, normalizedItem.key, normalizedItem)
}

export function registerForumRealtimeEvent(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(forumRealtimeEvents, normalizedItem.key, normalizedItem)
}

export function getForumRealtimeEvents(context = {}) {
  return orderedRegisteredItems(forumRealtimeEvents)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export async function runForumRuntimeHook(name, context = {}) {
  const normalizedName = String(name || '').trim()
  if (!normalizedName) {
    return []
  }

  const results = []
  for (const item of orderedRegisteredItems(forumRuntimeHooks)) {
    if (!isRegisteredItemEnabled(item, context)) {
      continue
    }
    const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
    if (!isVisible) {
      continue
    }

    const handler = item[normalizedName]
    if (typeof handler !== 'function') {
      continue
    }
    try {
      results.push(await handler(context))
    } catch (error) {
      if (typeof console !== 'undefined' && typeof console.error === 'function') {
        console.error(`论坛运行时扩展钩子执行失败: ${normalizedName}`, error)
      }
      results.push({
        key: item.key,
        error,
      })
    }
  }
  return results
}

export function getUiCopy(context = {}) {
  const resolvedItems = orderedRegisteredItems(uiCopies)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)

  if (!resolvedItems.length) {
    return null
  }

  const currentSurface = String(context.surface || '').trim()
  if (!currentSurface) {
    return resolvedItems[0]
  }

  const surfaceSpecificItem = resolvedItems.find(item => Array.isArray(item.surfaces) && item.surfaces.includes(currentSurface))
  return surfaceSpecificItem || resolvedItems[0]
}

export async function runComposerSubmitGuards(context = {}) {
  const guards = orderedRegisteredItems(composerSubmitGuards)

  for (const guard of guards) {
    if (!isRegisteredItemEnabled(guard, context)) {
      continue
    }
    const isVisible = typeof guard.isVisible === 'function' ? guard.isVisible(context) : true
    if (!isVisible) {
      continue
    }

    const result = typeof guard.check === 'function'
      ? await guard.check(context)
      : true

    if (result === false) {
      return {
        key: guard.key,
        message: guard.message || '提交已取消。',
        tone: guard.tone || 'error',
      }
    }

    if (result && typeof result === 'object') {
      return {
        key: guard.key,
        tone: guard.tone || 'error',
        ...result,
      }
    }
  }

  return null
}

export async function runComposerPayloadContributors(payload = {}, context = {}) {
  let nextPayload = payload && typeof payload === 'object' ? payload : {}
  const contributors = orderedRegisteredItems(composerPayloadContributors)

  for (const contributor of contributors) {
    if (!isRegisteredItemEnabled(contributor, context)) {
      continue
    }
    const isVisible = typeof contributor.isVisible === 'function' ? contributor.isVisible(context) : true
    if (!isVisible || typeof contributor.contribute !== 'function') {
      continue
    }

    const result = await contributor.contribute({
      ...context,
      payload: nextPayload,
    })
    if (result && typeof result === 'object') {
      nextPayload = result
    }
  }

  return nextPayload
}

export async function runComposerInitialStateContributors(initialState = {}, context = {}) {
  let nextState = normalizeComposerInitialState(initialState)
  const contributors = orderedRegisteredItems(composerInitialStateContributors)

  for (const contributor of contributors) {
    if (!isRegisteredItemEnabled(contributor, context)) {
      continue
    }
    const isVisible = typeof contributor.isVisible === 'function' ? contributor.isVisible(context) : true
    if (!isVisible || typeof contributor.contribute !== 'function') {
      continue
    }

    const result = await contributor.contribute({
      ...context,
      initialState: nextState,
    })
    if (result && typeof result === 'object') {
      nextState = mergeComposerInitialState(nextState, result)
    }
  }

  return nextState
}

export async function runComposerSubmitSuccess(context = {}) {
  const handlers = orderedRegisteredItems(composerSubmitSuccessHandlers)
  let handledCount = 0

  for (const handler of handlers) {
    if (!isRegisteredItemEnabled(handler, context)) {
      continue
    }
    const isVisible = typeof handler.isVisible === 'function' ? handler.isVisible(context) : true
    if (!isVisible) {
      continue
    }

    if (typeof handler.run === 'function') {
      await handler.run(context)
      handledCount += 1
    }
  }

  return handledCount
}

function normalizeComposerInitialState(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? {
        ...value,
        extensions: normalizeExtensionState(value.extensions || value.extensionState),
      }
    : { extensions: {} }
}

function mergeComposerInitialState(current, next) {
  const normalizedNext = normalizeComposerInitialState(next)
  return {
    ...current,
    ...normalizedNext,
    extensions: mergeExtensionState(current.extensions, normalizedNext.extensions),
  }
}

function normalizeExtensionState(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }

  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => String(key || '').trim())
      .map(([key, state]) => [
        String(key).trim(),
        state && typeof state === 'object' && !Array.isArray(state) ? { ...state } : state,
      ])
  )
}

function mergeExtensionState(current = {}, next = {}) {
  const normalizedCurrent = normalizeExtensionState(current)
  const normalizedNext = normalizeExtensionState(next)
  const merged = { ...normalizedCurrent }

  for (const [key, value] of Object.entries(normalizedNext)) {
    const currentValue = merged[key]
    if (
      currentValue &&
      typeof currentValue === 'object' &&
      !Array.isArray(currentValue) &&
      value &&
      typeof value === 'object' &&
      !Array.isArray(value)
    ) {
      merged[key] = {
        ...currentValue,
        ...value,
      }
      continue
    }
    merged[key] = value
  }

  return merged
}

export async function runComposerPreviewTransformers(context = {}) {
  const transformers = orderedRegisteredItems(composerPreviewTransformers)

  let transformed = {
    ...context,
    html: String(context.html || ''),
  }

  for (const transformer of transformers) {
    if (!isRegisteredItemEnabled(transformer, transformed)) {
      continue
    }
    const isVisible = typeof transformer.isVisible === 'function' ? transformer.isVisible(transformed) : true
    if (!isVisible) {
      continue
    }

    if (typeof transformer.transform !== 'function') {
      continue
    }

    const result = await transformer.transform(transformed)
    if (typeof result === 'string') {
      transformed = {
        ...transformed,
        html: result,
      }
      continue
    }

    if (result && typeof result === 'object') {
      transformed = {
        ...transformed,
        ...result,
        html: String(result.html ?? transformed.html ?? ''),
      }
    }
  }

  return transformed
}
