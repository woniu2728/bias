const forumNavItems = []
const discussionActionItems = []
const discussionActionHandlers = []
const postActionItems = []
const postActionHandlers = []
const headerItems = []
const forumNavSections = []
const composerTools = []
const composerNotices = []
const composerSubmitGuards = []
const composerSecondaryActions = []
const composerStatusItems = []
const composerDraftMetaItems = []
const composerSubmitSuccessHandlers = []
const composerMentionProviders = []
const composerPreviewTransformers = []
const profilePanels = []
const notificationRenderers = []
const searchSources = []
const userBadges = []
const discussionBadges = []
const discussionStateBadges = []
const postStateBadges = []
const heroMetaItems = []
const discussionReplyStates = []
const postReviewBanners = []
const discussionReviewBanners = []
const postFlagPanels = []
const approvalNotes = []
const emptyStates = []
const pageStates = []
const stateBlocks = []
const uiCopies = []

import { getCurrentExtensionId } from '../common/extensionRuntime.js'
import ItemList from '../common/itemList.js'

const registryTargets = [
  forumNavItems,
  discussionActionItems,
  discussionActionHandlers,
  postActionItems,
  postActionHandlers,
  headerItems,
  forumNavSections,
  composerTools,
  composerNotices,
  composerSubmitGuards,
  composerSecondaryActions,
  composerStatusItems,
  composerDraftMetaItems,
  composerSubmitSuccessHandlers,
  composerMentionProviders,
  composerPreviewTransformers,
  profilePanels,
  notificationRenderers,
  searchSources,
  userBadges,
  discussionBadges,
  discussionStateBadges,
  postStateBadges,
  heroMetaItems,
  discussionReplyStates,
  postReviewBanners,
  discussionReviewBanners,
  postFlagPanels,
  approvalNotes,
  emptyStates,
  pageStates,
  stateBlocks,
  uiCopies,
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

export function registerComposerMentionProvider(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerMentionProviders, normalizedItem.key, normalizedItem)
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

export function registerApprovalNote(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(approvalNotes, normalizedItem.key, normalizedItem)
}

export function getApprovalNote(context = {}) {
  const resolvedItems = orderedRegisteredItems(approvalNotes)
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

export async function runComposerSubmitSuccess(context = {}) {
  const handlers = orderedRegisteredItems(composerSubmitSuccessHandlers)

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
    }
  }
}

export async function runComposerMentionProviders(context = {}) {
  const providers = orderedRegisteredItems(composerMentionProviders)

  const items = []
  const seenKeys = new Set()

  for (const provider of providers) {
    if (!isRegisteredItemEnabled(provider, context)) {
      continue
    }
    const isVisible = typeof provider.isVisible === 'function' ? provider.isVisible(context) : true
    if (!isVisible) {
      continue
    }

    const result = typeof provider.search === 'function'
      ? await provider.search(context)
      : []

    if (!Array.isArray(result)) {
      continue
    }

    for (const item of result) {
      if (!item) {
        continue
      }
      const itemKey = String(item.id ?? item.username ?? item.key ?? '')
      if (itemKey && seenKeys.has(itemKey)) {
        continue
      }
      if (itemKey) {
        seenKeys.add(itemKey)
      }
      items.push(item)
    }
  }

  return items
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
