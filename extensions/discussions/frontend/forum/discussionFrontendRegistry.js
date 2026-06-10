import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  getFirstSurfaceAwareItem,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

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

const registryTargets = [
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
]

let uiCopyResolver = null

export function configureDiscussionRuntime({ getUiCopy } = {}) {
  uiCopyResolver = typeof getUiCopy === 'function' ? getUiCopy : uiCopyResolver
}

export function clearDiscussionRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
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

export function registerDiscussionReplyState(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReplyStates, normalizedItem.key, normalizedItem)
}

export function getDiscussionReplyState(context = {}) {
  return getFirstSurfaceAwareItem(discussionReplyStates, context)
}

export function registerDiscussionReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(discussionReviewBanners, normalizedItem.key, normalizedItem)
}

export function getDiscussionReviewBanner(context = {}) {
  return getFirstSurfaceAwareItem(discussionReviewBanners, context)
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

export function resolveDiscussionAction(actionKey, context = {}) {
  return getDiscussionActions(context).find(item => item.key === actionKey) || null
}

export async function runDiscussionAction(item, context = {}) {
  return runRegisteredAction(item, context, 'discussionActionHandlers')
}

async function runRegisteredAction(item, context = {}, handlerKey = '') {
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

  const registeredHandler = getDiscussionActionHandler(actionKey, context)
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
  return uiCopyResolver?.({ surface })?.text || fallback
}
