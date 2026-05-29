import ApprovalQueuePage from '../views/ApprovalQueuePage.vue'
import CoreExtensionHostPage from '../views/CoreExtensionHostPage.vue'
import FlagsPage from '../views/FlagsPage.vue'
import TagsPage from '../views/TagsPage.vue'
import UsersPage from '../views/UsersPage.vue'

export const builtinAdminEntries = {
  'builtin:core': {
    resolveSettingsPage: () => CoreExtensionHostPage,
    resolveOperationsPage: () => CoreExtensionHostPage,
  },
  'builtin:discussions': {},
  'builtin:posts': {},
  'builtin:approval': {
    resolveOperationsPage: () => ApprovalQueuePage,
  },
  'builtin:flags': {
    resolveOperationsPage: () => FlagsPage,
  },
  'builtin:tags': {
    resolveSettingsPage: () => TagsPage,
  },
  'builtin:users': {
    resolveOperationsPage: () => UsersPage,
  },
  'builtin:notifications': {},
  'builtin:mentions': {},
  'builtin:subscriptions': {},
  'builtin:realtime': {},
  'builtin:likes': {},
  'builtin:tag-stats': {},
}
