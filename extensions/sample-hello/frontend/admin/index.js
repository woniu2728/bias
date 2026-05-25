import SampleHelloDetailPage from './SampleHelloDetailPage.vue'
import SampleHelloOperationsPage from './SampleHelloOperationsPage.vue'
import SampleHelloSettingsPage from './SampleHelloSettingsPage.vue'

export function resolveDetailPage() {
  return SampleHelloDetailPage
}

export function resolveSettingsPage() {
  return SampleHelloSettingsPage
}

export function resolvePermissionsPage() {
  return SampleHelloSettingsPage
}

export function resolveOperationsPage() {
  return SampleHelloOperationsPage
}
