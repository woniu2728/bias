const forumNavItems = []
const forumSidebarSections = []
const discussionListContextItems = []
const discussionListRequestItems = []
const discussionListHeroItems = []
const discussionActionItems = []
const discussionActionHandlers = []
const postActionItems = []
const postActionHandlers = []
const headerItems = []
const forumNavSections = []
const composerTools = []
const composerFields = []
const composerNotices = []
const composerSubmitGuards = []
const composerPayloadContributors = []
const composerInitialStateContributors = []
const composerSecondaryActions = []
const composerStatusItems = []
const composerDraftMetaItems = []
const composerSubmitSuccessHandlers = []
const composerAutocompleteProviders = []
const composerPreviewTransformers = []
const profilePanels = []
const notificationRenderers = []
const searchSources = []
const searchModalSections = []
const userBadges = []
const discussionBadges = []
const discussionStateBadges = []
const discussionPresentationItems = []
const postStateBadges = []
const heroMetaItems = []
const discussionReplyStates = []
const postReviewBanners = []
const discussionReviewBanners = []
const postFlagPanels = []
const feedbackNotes = []
const emptyStates = []
const pageStates = []
const stateBlocks = []
const uiCopies = []
const forumRuntimeHooks = []
const forumRealtimeEvents = []

import { getCurrentExtensionId } from '../common/extensionRuntime.js'
import ItemList from '../common/itemList.js'

const registryTargets = [
  forumNavItems,
  forumSidebarSections,
  discussionListContextItems,
  discussionListRequestItems,
  discussionListHeroItems,
  discussionActionItems,
  discussionActionHandlers,
  postActionItems,
  postActionHandlers,
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
  profilePanels,
  notificationRenderers,
  searchSources,
  searchModalSections,
  userBadges,
  discussionBadges,
  discussionStateBadges,
  discussionPresentationItems,
  postStateBadges,
  heroMetaItems,
  discussionReplyStates,
  postReviewBanners,
  discussionReviewBanners,
  postFlagPanels,
  feedbackNotes,
  emptyStates,
  pageStates,
  stateBlocks,
  uiCopies,
  forumRuntimeHooks,
  forumRealtimeEvents,
]

function upsertByKey(target, key, value) {
  const existingIndex = target.findIndex(item => item.key === key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function orderedRegisteredItems(target) {
  const items = new ItemList()
  target.forEach((item, index) => {
    const key = String(item?.key || item?.name || item?.type || index).trim()
    items.add(key, item, -(Number(item?.order ?? item?.priority ?? 100) || 100))
  })
  return items.toArray()
}

function normalizeRegisteredItem(item, defaults = {}) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  const extensionId = String(item?.extensionId || item?.extension_id || getCurrentExtensionId() || '').trim()
  return {
    order: 100,
    surfaces: [],
    ...defaults,
    ...item,
    ...(moduleId ? { moduleId, module_id: moduleId } : {}),
    ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
  }
}

export function clearForumRegistryExtensions(extensionId = '') {
  const normalizedExtensionId = String(extensionId || '').trim()
  for (const target of registryTargets) {
    for (let index = target.length - 1; index >= 0; index -= 1) {
      const itemExtensionId = String(target[index]?.extensionId || target[index]?.extension_id || '').trim()
      if (!itemExtensionId) {
        continue
      }
      if (!normalizedExtensionId || itemExtensionId === normalizedExtensionId) {
        target.splice(index, 1)
      }
    }
  }
}

function isRegisteredItemEnabled(item, context = {}) {
  const moduleId = String(item?.moduleId || item?.module_id || '').trim()
  if (!moduleId) {
    return true
  }

  const checker = context.forumStore?.isModuleEnabled
  if (typeof checker === 'function') {
    return checker(moduleId)
  }

  return true
}

function resolveRegisteredItem(item, context = {}) {
  if (!isRegisteredItemEnabled(item, context)) {
    return null
  }

  if (Array.isArray(item.surfaces) && item.surfaces.length > 0) {
    const currentSurface = String(context.surface || '').trim()
    if (!currentSurface || !item.surfaces.includes(currentSurface)) {
      return null
    }
  }

  const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
  if (!isVisible) {
    return null
  }

  const resolvedItem = typeof item.resolve === 'function'
    ? item.resolve(context)
    : item

  if (!resolvedItem) {
    return null
  }

  const getResolvedValue = field => {
    if (field in resolvedItem) {
      const value = resolvedItem[field]
      return typeof value === 'function' ? value(context) : value
    }

    const fallback = item[field]
    return typeof fallback === 'function' ? fallback(context) : fallback
  }

  return {
    ...item,
    ...resolvedItem,
    icon: getResolvedValue('icon'),
    label: getResolvedValue('label'),
    title: getResolvedValue('title'),
    tone: getResolvedValue('tone'),
    to: getResolvedValue('to'),
    href: getResolvedValue('href'),
    badge: getResolvedValue('badge'),
    count: getResolvedValue('count'),
    component: getResolvedValue('component'),
    componentProps: getResolvedValue('componentProps') || {},
    active: Boolean(
      'isActive' in resolvedItem
        ? (typeof resolvedItem.isActive === 'function' ? resolvedItem.isActive(context) : resolvedItem.active)
        : (typeof item.isActive === 'function' ? item.isActive(context) : item.active)
    ),
    description: getResolvedValue('description'),
    disabledReason: getResolvedValue('disabledReason'),
    confirm: getResolvedValue('confirm'),
    disabled: Boolean(
      'isDisabled' in resolvedItem
        ? (typeof resolvedItem.isDisabled === 'function' ? resolvedItem.isDisabled(context) : resolvedItem.disabled)
        : (typeof item.isDisabled === 'function' ? item.isDisabled(context) : item.disabled)
    ),
  }
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
  const normalizedItem = normalizeRegisteredItem(item, {
    icon: 'fas fa-bell',
    navigationScope: 'notifications',
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

export function registerSearchModalSection(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(searchModalSections, normalizedItem.key, normalizedItem)
}

export function getSearchModalSections(context = {}) {
  return orderedRegisteredItems(searchModalSections)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
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
  const resolvedItems = orderedRegisteredItems(discussionReplyStates)
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

export function registerPostReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postReviewBanners, normalizedItem.key, normalizedItem)
}

export function getPostReviewBanner(context = {}) {
  const resolvedItems = orderedRegisteredItems(postReviewBanners)
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

export function registerDiscussionReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReviewBanners, normalizedItem.key, normalizedItem)
}

export function getDiscussionReviewBanner(context = {}) {
  const resolvedItems = orderedRegisteredItems(discussionReviewBanners)
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

export function registerPostFlagPanel(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postFlagPanels, normalizedItem.key, normalizedItem)
}

export function getPostFlagPanel(context = {}) {
  const resolvedItems = orderedRegisteredItems(postFlagPanels)
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

export function registerFeedbackNote(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(feedbackNotes, normalizedItem.key, normalizedItem)
}

export function getFeedbackNote(context = {}) {
  const resolvedItems = orderedRegisteredItems(feedbackNotes)
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

export function registerEmptyState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(emptyStates, normalizedItem.key, normalizedItem)
}

export function getEmptyState(context = {}) {
  const resolvedItems = orderedRegisteredItems(emptyStates)
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

export function registerPageState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(pageStates, normalizedItem.key, normalizedItem)
}

export function getPageState(context = {}) {
  const resolvedItems = orderedRegisteredItems(pageStates)
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

export function registerStateBlock(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(stateBlocks, normalizedItem.key, normalizedItem)
}

export function getStateBlock(context = {}) {
  const resolvedItems = orderedRegisteredItems(stateBlocks)
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
