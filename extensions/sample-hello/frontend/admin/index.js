import SampleHelloOperationsPage from './SampleHelloOperationsPage.vue'
import SampleHelloSettingsPage from './SampleHelloSettingsPage.vue'

export function resolveSettingsPage() {
  return SampleHelloSettingsPage
}

export function resolvePermissionsPage() {
  return SampleHelloSettingsPage
}

export function resolveOperationsPage() {
  return SampleHelloOperationsPage
}
