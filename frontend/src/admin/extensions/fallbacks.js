import ExtensionGeneratedSettingsPage from '../views/ExtensionGeneratedSettingsPage.vue'

export async function resolveFallbackExtensionSettingsPage({ extension, surface }) {
  if (surface !== 'settings') {
    return null
  }
  if (!Array.isArray(extension?.settings_schema) || !extension.settings_schema.length) {
    return null
  }
  return ExtensionGeneratedSettingsPage
}
