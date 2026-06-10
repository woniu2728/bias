import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

const forumRealtimeEvents = getFrontendRegistrySlot('realtime.forumEvents')
const registryTargets = [forumRealtimeEvents]

export function clearRealtimeRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
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
