import ApprovalQueuePage from '../views/ApprovalQueuePage.vue'
import DiscussionsExtensionHostPage from '../views/DiscussionsExtensionHostPage.vue'
import FlagsPage from '../views/FlagsPage.vue'
import LikesExtensionHostPage from '../views/LikesExtensionHostPage.vue'
import MentionsExtensionHostPage from '../views/MentionsExtensionHostPage.vue'
import NotificationsExtensionHostPage from '../views/NotificationsExtensionHostPage.vue'
import PostsExtensionHostPage from '../views/PostsExtensionHostPage.vue'
import RealtimeExtensionHostPage from '../views/RealtimeExtensionHostPage.vue'
import SubscriptionsExtensionHostPage from '../views/SubscriptionsExtensionHostPage.vue'
import TagStatsExtensionHostPage from '../views/TagStatsExtensionHostPage.vue'
import TagsPage from '../views/TagsPage.vue'
import UsersPage from '../views/UsersPage.vue'

export const builtinAdminEntries = {
  'builtin:discussions': {
    resolvePermissionsPage: () => DiscussionsExtensionHostPage,
    resolveOperationsPage: () => DiscussionsExtensionHostPage,
  },
  'builtin:posts': {
    resolveOperationsPage: () => PostsExtensionHostPage,
  },
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
  'builtin:notifications': {
    resolveOperationsPage: () => NotificationsExtensionHostPage,
  },
  'builtin:mentions': {
    resolveOperationsPage: () => MentionsExtensionHostPage,
  },
  'builtin:subscriptions': {
    resolveOperationsPage: () => SubscriptionsExtensionHostPage,
  },
  'builtin:realtime': {
    resolveOperationsPage: () => RealtimeExtensionHostPage,
  },
  'builtin:likes': {
    resolveOperationsPage: () => LikesExtensionHostPage,
  },
  'builtin:tag-stats': {
    resolveOperationsPage: () => TagStatsExtensionHostPage,
  },
}
