import ApprovalQueuePage from '../views/ApprovalQueuePage.vue'
import FlagsPage from '../views/FlagsPage.vue'
import UsersPage from '../views/UsersPage.vue'

const load = importer => async () => {
  const module = await importer()
  return module.default || module
}

const discussionsHost = load(() => import('../views/DiscussionsExtensionHostPage.vue'))
const postsHost = load(() => import('../views/PostsExtensionHostPage.vue'))
const notificationsHost = load(() => import('../views/NotificationsExtensionHostPage.vue'))
const mentionsHost = load(() => import('../views/MentionsExtensionHostPage.vue'))
const subscriptionsHost = load(() => import('../views/SubscriptionsExtensionHostPage.vue'))
const realtimeHost = load(() => import('../views/RealtimeExtensionHostPage.vue'))
const likesHost = load(() => import('../views/LikesExtensionHostPage.vue'))
const tagStatsHost = load(() => import('../views/TagStatsExtensionHostPage.vue'))

export const builtinAdminEntries = {
  'builtin:discussions': {
    resolvePermissionsPage: discussionsHost,
    resolveOperationsPage: discussionsHost,
  },
  'builtin:posts': {
    resolveOperationsPage: postsHost,
  },
  'builtin:approval': {
    resolveOperationsPage: () => ApprovalQueuePage,
  },
  'builtin:flags': {
    resolveOperationsPage: () => FlagsPage,
  },
  'builtin:users': {
    resolveOperationsPage: () => UsersPage,
  },
  'builtin:notifications': {
    resolveOperationsPage: notificationsHost,
  },
  'builtin:mentions': {
    resolveOperationsPage: mentionsHost,
  },
  'builtin:subscriptions': {
    resolveOperationsPage: subscriptionsHost,
  },
  'builtin:realtime': {
    resolveOperationsPage: realtimeHost,
  },
  'builtin:likes': {
    resolveOperationsPage: likesHost,
  },
  'builtin:tag-stats': {
    resolveOperationsPage: tagStatsHost,
  },
}
