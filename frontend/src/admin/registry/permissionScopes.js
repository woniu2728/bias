import { createListItemRegistry } from './shared.js'

const permissionScopeRegistry = createListItemRegistry({
  order: 100,
  surface: 'admin-permissions',
})

export const registerAdminPermissionScope = permissionScopeRegistry.register
export const getAdminPermissionScopes = permissionScopeRegistry.get
