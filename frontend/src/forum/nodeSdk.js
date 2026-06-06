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
  getNotificationRenderers,
  getStateBlock,
  getUiCopy,
  registerComposerAutocompleteProvider,
  registerEmptyState,
} from './frontendRegistry.js'
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
  getTrackedDiscussionIdsFromDiscussionItems,
  getTrackedDiscussionIdsFromPostItems,
  hasTrackedDiscussionId,
  mergeForumEventPayload,
  shouldRefreshForumEvent,
} from '../utils/forumRealtime.js'
export {
  renderTwemojiHtml,
  renderTwemojiText,
  setTwemojiBaseUrl,
  setTwemojiEnabled,
} from '../utils/twemoji.js'
export const PostReportModal = null
export * from '../common/sdk.js'
