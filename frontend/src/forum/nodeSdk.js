import api from '../api/index.js'

export const forumApi = api

export {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
  useRoute,
  useRouter,
} from './vueRuntime.js'
export {
  usePaginatedListState,
  useRouteListState,
  useRoutePagination,
  useStartDiscussionAction,
} from './routeRuntime.js'
export {
  getComposerAutocompleteProviders,
  getEmptyState,
  getForumRealtimeEvents,
  getNotificationRenderers,
  getStateBlock,
  getUiCopy,
  registerComposerAutocompleteProvider,
  registerEmptyState,
  registerForumRealtimeEvent,
} from './frontendRegistry.js'
export const ModerationActionModal = null
export { defineStore } from 'pinia'
export { registerResourceNormalizer, useResourceStore } from '../stores/resource.js'
export {
  getTextareaCaretCoordinates,
} from '../utils/composer.js'
export {
  buildDiscussionPath,
  buildUserPath,
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  normalizeDiscussion,
  normalizePost,
  normalizeUser,
  unwrapList,
} from '../utils/forum.js'
export {
  FORUM_REALTIME_REFRESH_EVENT_TYPES,
  getForumRealtimeEventPolicy,
  getTrackedDiscussionIdsFromDiscussionItems,
  getTrackedDiscussionIdsFromPostItems,
  hasTrackedDiscussionId,
  mergeForumEventPayload,
  shouldAppendForumRealtimePost,
  shouldMarkForumEventAsNewReply,
  shouldRefreshForumEvent,
  shouldUpsertForumRealtimePost,
} from '../utils/forumRealtime.js'
export {
  highlightSearchText,
} from '../utils/search.js'
export {
  renderTwemojiHtml,
  renderTwemojiText,
  setTwemojiBaseUrl,
  setTwemojiEnabled,
} from '../utils/twemoji.js'
export * from '../common/sdk.js'
