import ExtensionGeneratedSettingsPage from '../views/ExtensionGeneratedSettingsPage.vue'
import ExtensionGeneratedPermissionsPage from '../views/ExtensionGeneratedPermissionsPage.vue'
import ExtensionGeneratedOperationsPage from '../views/ExtensionGeneratedOperationsPage.vue'

export async function resolveFallbackExtensionSettingsPage({ extension, surface }) {
  if (surface !== 'settings') {
    return null
  }
  if (!Array.isArray(extension?.settings_pages) || !extension.settings_pages.length) {
    return null
  }
  return ExtensionGeneratedSettingsPage
}

export async function resolveFallbackExtensionPermissionsPage({ extension, surface }) {
  if (surface !== 'permissions') {
    return null
  }
  if (!extension?.action_links?.permissions_page) {
    return null
  }
  return ExtensionGeneratedPermissionsPage
}

export async function resolveFallbackExtensionOperationsPage({ extension, surface }) {
  if (surface !== 'operations') {
    return null
  }
  const hasAdminActions = Array.isArray(extension?.admin_actions) && extension.admin_actions.length > 0
  const hasRuntimeActions = Array.isArray(extension?.runtime_actions) && extension.runtime_actions.length > 0
  if (!hasAdminActions && !hasRuntimeActions) {
    return null
  }
  return ExtensionGeneratedOperationsPage
}
