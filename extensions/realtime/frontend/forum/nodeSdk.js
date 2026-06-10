export function useForumRealtimeStore() {
  return {
    connectionState: { value: 'idle' },
    connectionFailureCount: { value: 0 },
    hasConnectionError: { value: false },
    isConnected: { value: false },
    isReconnecting: { value: false },
    connect() {},
    disconnect() {},
    getTypingUsers() { return [] },
    resetState() {},
    sendTypingIndicator() { return false },
    trackDiscussionIds() {},
    untrackDiscussionIds() {},
  }
}

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
} from './forumRealtime.js'
export {
  getForumRealtimeEvents,
  registerForumRealtimeEvent,
} from './realtimeFrontendRegistry.js'
