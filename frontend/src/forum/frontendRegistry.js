const forumNavItems = []
const discussionActionItems = []
const postActionItems = []
const headerItems = []
const forumNavSections = []
const composerTools = []
const composerNotices = []
const composerSubmitGuards = []

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
    if (currentSurface && !item.surfaces.includes(currentSurface)) {
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

  return {
    ...item,
    ...resolvedItem,
    to: typeof resolvedItem.to === 'function' ? resolvedItem.to(context) : resolvedItem.to,
    href: typeof resolvedItem.href === 'function' ? resolvedItem.href(context) : resolvedItem.href,
    badge: typeof resolvedItem.badge === 'function' ? resolvedItem.badge(context) : resolvedItem.badge,
    description: typeof resolvedItem.description === 'function' ? resolvedItem.description(context) : resolvedItem.description,
    disabledReason: typeof resolvedItem.disabledReason === 'function' ? resolvedItem.disabledReason(context) : resolvedItem.disabledReason,
    confirm: typeof resolvedItem.confirm === 'function' ? resolvedItem.confirm(context) : resolvedItem.confirm,
    disabled: Boolean(
      typeof resolvedItem.isDisabled === 'function'
        ? resolvedItem.isDisabled(context)
        : resolvedItem.disabled
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
