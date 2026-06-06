import {
  clearListRegistriesForExtension,
  createListItemRegistry as createCommonListItemRegistry,
  createSingleItemRegistry as createCommonSingleItemRegistry,
} from '../../common/listRegistry.js'

export function clearAdminRegistryExtensions(extensionId = '') {
  clearListRegistriesForExtension(extensionId)
}

export function createSingleItemRegistry(defaults = {}) {
  return createCommonSingleItemRegistry(defaults)
}

export function createListItemRegistry(defaults = {}) {
  return createCommonListItemRegistry(defaults)
}
