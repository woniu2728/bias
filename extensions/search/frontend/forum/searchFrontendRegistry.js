import {
  clearRegistryExtensions,
  getFrontendRegistrySlot,
  getFirstSurfaceAwareItem,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from '@bias/core'

const searchSources = getFrontendRegistrySlot('search.sources')
const searchModalProviders = getFrontendRegistrySlot('search.modalProviders')
const searchModalSections = getFrontendRegistrySlot('search.modalSections')
const registryTargets = [
  searchSources,
  searchModalProviders,
  searchModalSections,
]

export function clearSearchRegistryExtensions(extensionId = '') {
  clearRegistryExtensions(registryTargets, extensionId)
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

export function getSearchModalSection(context = {}) {
  return getFirstSurfaceAwareItem(searchModalSections, context)
}
