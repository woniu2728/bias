const forumNavItems = []
const discussionActionItems = []
const postActionItems = []
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

function upsertByKey(target, key, value) {
  const existingIndex = target.findIndex(item => item.key === key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function normalizeRegisteredItem(item, defaults = {}) {
  return {
    order: 100,
    surfaces: [],
    ...defaults,
    ...item,
  }
}

function resolveRegisteredItem(item, context = {}) {
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
  return [...forumNavItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function getForumNavSections(context = {}) {
  const items = getForumNavItems(context)
  const sectionMap = new Map(
    [...forumNavSections]
      .sort((left, right) => (left.order || 100) - (right.order || 100))
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

export function getDiscussionActions(context = {}) {
  return [...discussionActionItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostAction(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postActionItems, normalizedItem.key, normalizedItem)
}

export function getPostActions(context = {}) {
  return [...postActionItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  return [...headerItems]
    .filter(item => !placement || item.placement === placement)
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerTool(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerTools, normalizedItem.key, normalizedItem)
}

export function getComposerTools(context = {}) {
  return [...composerTools]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerNotice(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerNotices, normalizedItem.key, normalizedItem)
}

export function getComposerNotices(context = {}) {
  return [...composerNotices]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  return [...composerSecondaryActions]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerStatusItem(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerStatusItems, normalizedItem.key, normalizedItem)
}

export function getComposerStatusItems(context = {}) {
  return [...composerStatusItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerComposerDraftMeta(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(composerDraftMetaItems, normalizedItem.key, normalizedItem)
}

export function getComposerDraftMeta(context = {}) {
  return [...composerDraftMetaItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  return [...profilePanels]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  return [...notificationRenderers]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  return [...searchSources]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerUserBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(userBadges, normalizedItem.key, normalizedItem)
}

export function getUserBadges(context = {}) {
  return [...userBadges]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionBadges, normalizedItem.key, normalizedItem)
}

export function getDiscussionBadges(context = {}) {
  return [...discussionBadges]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionStateBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionStateBadges, normalizedItem.key, normalizedItem)
}

export function getDiscussionStateBadges(context = {}) {
  return [...discussionStateBadges]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostStateBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postStateBadges, normalizedItem.key, normalizedItem)
}

export function getPostStateBadges(context = {}) {
  return [...postStateBadges]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerHeroMeta(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(heroMetaItems, normalizedItem.key, normalizedItem)
}

export function getHeroMetaItems(context = {}) {
  return [...heroMetaItems]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerDiscussionReplyState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReplyStates, normalizedItem.key, normalizedItem)
}

export function getDiscussionReplyState(context = {}) {
  const resolvedItems = [...discussionReplyStates]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...postReviewBanners]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...discussionReviewBanners]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...postFlagPanels]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...approvalNotes]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...emptyStates]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...pageStates]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...stateBlocks]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const resolvedItems = [...uiCopies]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
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
  const guards = [...composerSubmitGuards]
    .sort((left, right) => (left.order || 100) - (right.order || 100))

  for (const guard of guards) {
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
  const handlers = [...composerSubmitSuccessHandlers]
    .sort((left, right) => (left.order || 100) - (right.order || 100))

  for (const handler of handlers) {
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
  const providers = [...composerMentionProviders]
    .sort((left, right) => (left.order || 100) - (right.order || 100))

  const items = []
  const seenKeys = new Set()

  for (const provider of providers) {
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
  const transformers = [...composerPreviewTransformers]
    .sort((left, right) => (left.order || 100) - (right.order || 100))

  let transformed = {
    ...context,
    html: String(context.html || ''),
  }

  for (const transformer of transformers) {
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
