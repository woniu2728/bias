import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  getFirstSurfaceAwareItem,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

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

const registryTargets = [
  postActionItems,
  postActionHandlers,
  postStateBadges,
  postReviewBanners,
  postFlagPanels,
  postTypeDefinitions,
]

let uiCopyResolver = null

export function configurePostRuntime({ getUiCopy } = {}) {
  uiCopyResolver = typeof getUiCopy === 'function' ? getUiCopy : uiCopyResolver
}

export function clearPostRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
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

export function registerPostStateBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postStateBadges, normalizedItem.key, normalizedItem)
}

export function getPostStateBadges(context = {}) {
  return orderedRegisteredItems(postStateBadges)
    .map(item => resolveRegisteredItem(item, context))
    .filter(Boolean)
}

export function registerPostReviewBanner(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postReviewBanners, normalizedItem.key, normalizedItem)
}

export function getPostReviewBanner(context = {}) {
  return getFirstSurfaceAwareItem(postReviewBanners, context)
}

export function registerPostFlagPanel(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(postFlagPanels, normalizedItem.key, normalizedItem)
}

export function getPostFlagPanel(context = {}) {
  return getFirstSurfaceAwareItem(postFlagPanels, context)
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

export function resolvePostAction(actionKey, context = {}) {
  return getPostActions(context).find(item => item.key === actionKey) || null
}

export async function runPostAction(item, context = {}) {
  return runRegisteredAction(item, context, 'postActionHandlers')
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

  const registeredHandler = getPostActionHandler(actionKey, context)
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
