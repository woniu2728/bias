import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

const profilePanels = getFrontendRegistrySlot('users.profilePanels')
const userBadges = getFrontendRegistrySlot('users.badges')
const authModalProviders = getFrontendRegistrySlot('users.authModalProviders')
const registryTargets = [
  profilePanels,
  userBadges,
  authModalProviders,
]

export function clearUserRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
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

export function registerUserBadge(item) {
  const normalizedItem = normalizeRegisteredItem(item)
  return upsertByKey(userBadges, normalizedItem.key, normalizedItem)
}

export function getUserBadges(context = {}) {
  return orderedRegisteredItems(userBadges)
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
